from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings
import logging

from .models import Notification, ECPointRequest, User, PointTransaction
# from .social_models import (
#     NotificationPreference, UserPrivacySettings, Friendship, 
#     SocialPost, PostComment, DetailedReview, BlockedUser
# )
from .email_service import email_service

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    """通知サービス"""
    
    def __init__(self):
        pass
    
    def notify_store_approval_request(self, ec_request: ECPointRequest):
        """店舗に承認依頼通知を送信"""
        try:
            # 店舗管理者を取得
            store_managers = ec_request.store.managers.filter(
                status='active',
                role='store_manager'
            )
            
            if not store_managers.exists():
                logger.warning(f"No active managers found for store {ec_request.store.name}")
                return False
            
            # 各管理者に通知を作成
            for manager in store_managers:
                self._create_notification(
                    user=manager,
                    notification_type='ec_approval_request',
                    title=f'ポイント付与承認依頼',
                    message=self._format_approval_request_message(ec_request),
                    email_template='ec_approval_request',
                    email_context=self._get_approval_request_context(ec_request),
                    priority='high'
                )
            
            logger.info(f"Approval request notifications sent for request {ec_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send approval request notifications: {str(e)}")
            return False
    
    def notify_user_points_awarded(self, ec_request: ECPointRequest, payment_method: str):
        """ユーザーにポイント付与完了通知を送信"""
        try:
            message = f"""
{ec_request.store.name}でのご購入により{ec_request.points_awarded}ポイントが付与されました。

購入金額: {ec_request.purchase_amount}円
付与ポイント: {ec_request.points_awarded}ポイント
注文ID: {ec_request.order_id}
支払方法: {payment_method}

ご利用ありがとうございました。
            """.strip()
            
            self._create_notification(
                user=ec_request.user,
                notification_type='point_received',
                title=f'{ec_request.points_awarded}ポイントが付与されました',
                message=message,
                email_template='points_awarded',
                email_context={
                    'user_name': ec_request.user.username,
                    'store_name': ec_request.store.name,
                    'purchase_amount': ec_request.purchase_amount,
                    'points_awarded': ec_request.points_awarded,
                    'order_id': ec_request.order_id,
                    'payment_method': payment_method,
                    'total_balance': ec_request.user.point_balance
                },
                priority='normal'
            )
            
            logger.info(f"Points awarded notification sent to user {ec_request.user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send points awarded notification: {str(e)}")
            return False
    
    def notify_user_rejection(self, ec_request: ECPointRequest):
        """ユーザーに申請拒否通知を送信"""
        try:
            message = f"""
{ec_request.store.name}でのポイント申請が拒否されました。

購入金額: {ec_request.purchase_amount}円
注文ID: {ec_request.order_id}
拒否理由: {ec_request.rejection_reason}

ご不明な点がございましたら、店舗またはサポートまでお問い合わせください。
            """.strip()
            
            self._create_notification(
                user=ec_request.user,
                notification_type='ec_request_rejected',
                title='ポイント申請が拒否されました',
                message=message,
                email_template='request_rejected',
                email_context={
                    'user_name': ec_request.user.username,
                    'store_name': ec_request.store.name,
                    'purchase_amount': ec_request.purchase_amount,
                    'order_id': ec_request.order_id,
                    'rejection_reason': ec_request.rejection_reason,
                    'contact_email': getattr(settings, 'SUPPORT_EMAIL', 'support@biid.jp')
                },
                priority='normal'
            )
            
            logger.info(f"Rejection notification sent to user {ec_request.user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send rejection notification: {str(e)}")
            return False
    
    def notify_deposit_low_balance(self, store, current_balance, threshold):
        """デポジット残高不足通知"""
        try:
            store_managers = store.managers.filter(
                status='active',
                role='store_manager'
            )
            
            for manager in store_managers:
                message = f"""
デポジット残高が設定値を下回りました。

現在残高: {current_balance}円
閾値: {threshold}円

ポイント付与に支障をきたす可能性があります。
デポジットのチャージをご検討ください。
                """.strip()
                
                self._create_notification(
                    user=manager,
                    notification_type='deposit_low_balance',
                    title='デポジット残高不足',
                    message=message,
                    email_template='deposit_low_balance',
                    email_context={
                        'manager_name': manager.username,
                        'store_name': store.name,
                        'current_balance': current_balance,
                        'threshold': threshold,
                        'deposit_url': f"{settings.FRONTEND_URL}/store/deposit"
                    },
                    priority='high'
                )
            
            logger.info(f"Low balance notifications sent for store {store.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send low balance notifications: {str(e)}")
            return False
    
    def notify_admin_suspicious_activity(self, detection, ec_request: ECPointRequest):
        """管理者に不審な活動を通知"""
        try:
            admin_users = User.objects.filter(role='admin', status='active')
            
            for admin in admin_users:
                message = f"""
不審な申請パターンが検知されました。

検知種別: {detection.get_detection_type_display()}
重要度: {detection.get_severity_display()}
ユーザー: {ec_request.user.username}
店舗: {ec_request.store.name}
申請ID: {ec_request.id}

詳細を確認してください。
                """.strip()
                
                self._create_notification(
                    user=admin,
                    notification_type='admin_alert',
                    title='不審な申請パターンを検知',
                    message=message,
                    email_template='suspicious_activity_alert',
                    email_context={
                        'admin_name': admin.username,
                        'detection_type': detection.get_detection_type_display(),
                        'severity': detection.get_severity_display(),
                        'user_name': ec_request.user.username,
                        'store_name': ec_request.store.name,
                        'request_id': ec_request.id,
                        'detection_details': detection.detection_details,
                        'admin_url': f"{settings.ADMIN_URL}/ec-requests/{ec_request.id}"
                    },
                    priority='urgent'
                )
            
            logger.info(f"Suspicious activity notifications sent for request {ec_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send suspicious activity notifications: {str(e)}")
            return False
    
    def notify_payment_failure(self, store, ec_request: ECPointRequest, error_message: str):
        """決済失敗通知"""
        try:
            store_managers = store.managers.filter(
                status='active',
                role='store_manager'
            )
            
            for manager in store_managers:
                message = f"""
ポイント購入の決済が失敗しました。

申請ID: {ec_request.id}
ユーザー: {ec_request.user.username}
必要ポイント: {ec_request.points_to_award}ポイント
エラー内容: {error_message}

デポジットから自動的に消費されます。
決済方法の確認をお願いします。
                """.strip()
                
                self._create_notification(
                    user=manager,
                    notification_type='payment_failure',
                    title='決済失敗通知',
                    message=message,
                    email_template='payment_failure',
                    email_context={
                        'manager_name': manager.username,
                        'store_name': store.name,
                        'request_id': ec_request.id,
                        'user_name': ec_request.user.username,
                        'points_required': ec_request.points_to_award,
                        'error_message': error_message,
                        'payment_settings_url': f"{settings.FRONTEND_URL}/store/payment-settings"
                    },
                    priority='high'
                )
            
            logger.info(f"Payment failure notifications sent for store {store.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send payment failure notifications: {str(e)}")
            return False
    
    def _create_notification(self, user: User, notification_type: str, title: str, 
                           message: str, email_template: str = None, 
                           email_context: dict = None, priority: str = 'normal'):
        """通知を作成"""
        try:
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                email_template=email_template or '',
                email_context=email_context or {},
                priority=priority
            )
            
            # メール送信が有効な場合
            if email_template and email_context and hasattr(email_service, 'send_notification_email'):
                try:
                    email_service.send_notification_email(notification)
                except Exception as e:
                    logger.error(f"Failed to send email for notification {notification.id}: {str(e)}")
            
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None
    
    def _format_approval_request_message(self, ec_request: ECPointRequest):
        """承認依頼メッセージをフォーマット"""
        request_type = "レシート申請" if ec_request.request_type == 'receipt' else "Webhook申請"
        
        message = f"""
新しいポイント付与申請が届いています。

申請種別: {request_type}
顧客: {ec_request.user.username}
購入金額: {ec_request.purchase_amount}円
予定ポイント: {ec_request.points_to_award}ポイント
注文ID: {ec_request.order_id}
申請日時: {ec_request.created_at.strftime('%Y年%m月%d日 %H:%M')}

管理画面から承認・拒否の処理をお願いします。
        """.strip()
        
        return message
    
    def _get_approval_request_context(self, ec_request: ECPointRequest):
        """承認依頼メール用コンテキスト"""
        return {
            'store_name': ec_request.store.name,
            'request_type': ec_request.get_request_type_display(),
            'customer_name': ec_request.user.username,
            'customer_email': ec_request.user.email,
            'purchase_amount': ec_request.purchase_amount,
            'estimated_points': ec_request.points_to_award,
            'order_id': ec_request.order_id,
            'purchase_date': ec_request.purchase_date.strftime('%Y年%m月%d日 %H:%M'),
            'created_at': ec_request.created_at.strftime('%Y年%m月%d日 %H:%M'),
            'has_receipt_image': bool(ec_request.receipt_image),
            'receipt_description': ec_request.receipt_description,
            'approval_url': f"{settings.FRONTEND_URL}/store/approvals/{ec_request.id}"
        }
    
    def send_bulk_notifications(self, users, notification_type: str, title: str, 
                              message: str, email_template: str = None, 
                              email_context: dict = None):
        """一括通知送信"""
        try:
            notifications = []
            
            for user in users:
                notification = Notification(
                    user=user,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    email_template=email_template or '',
                    email_context=email_context or {},
                    priority='normal'
                )
                notifications.append(notification)
            
            # 一括作成
            created_notifications = Notification.objects.bulk_create(notifications)
            
            # メール送信（一括処理）
            if email_template and hasattr(email_service, 'send_bulk_emails'):
                try:
                    email_service.send_bulk_emails(created_notifications)
                except Exception as e:
                    logger.error(f"Failed to send bulk emails: {str(e)}")
            
            logger.info(f"Sent {len(created_notifications)} bulk notifications")
            return len(created_notifications)
            
        except Exception as e:
            logger.error(f"Failed to send bulk notifications: {str(e)}")
            return 0
    
    def get_unread_count(self, user: User):
        """未読通知数を取得"""
        try:
            return Notification.objects.filter(
                user=user,
                is_read=False
            ).count()
        except Exception as e:
            logger.error(f"Failed to get unread count: {str(e)}")
            return 0
    
    def mark_as_read(self, notification_id: int, user: User):
        """通知を既読にマーク"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=user
            )
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            
            return True
        except Notification.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Failed to mark notification as read: {str(e)}")
            return False
    
    def cleanup_old_notifications(self, days: int = 90):
        """古い通知を削除"""
        try:
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            deleted_count = Notification.objects.filter(
                created_at__lt=cutoff_date,
                is_read=True
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} old notifications")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old notifications: {str(e)}")
            return 0