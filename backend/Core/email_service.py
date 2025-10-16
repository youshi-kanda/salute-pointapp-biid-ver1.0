from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Template, Context
from django.conf import settings
from django.utils import timezone
from django.db import transaction
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .models import Notification, EmailTemplate, EmailLog, User, Store

logger = logging.getLogger(__name__)


class EmailService:
    """メール送信サービス"""
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@biid.app')
        self.max_retry_count = 3
    
    def send_notification_email(self, notification: Notification) -> bool:
        """通知メールを送信"""
        try:
            if not notification.user.email:
                logger.warning(f"User {notification.user.id} has no email address")
                return False
            
            # テンプレートを取得
            template = self._get_template(notification.email_template or notification.notification_type)
            if not template:
                logger.error(f"Template not found for {notification.notification_type}")
                return False
            
            # コンテキストを準備
            context = self._prepare_context(notification)
            
            # メール送信
            success = self._send_email(
                template=template,
                context=context,
                recipient_email=notification.user.email,
                notification=notification
            )
            
            if success:
                notification.email_sent = True
                notification.email_sent_at = timezone.now()
                notification.save()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send notification email: {str(e)}")
            notification.email_error_message = str(e)
            notification.save()
            return False
    
    def send_store_registration_email(self, store: Store, admin_users: List[User]) -> bool:
        """店舗登録通知メールを管理者に送信"""
        try:
            template = self._get_template('store_registration_admin')
            if not template:
                logger.error("Store registration admin template not found")
                return False
            
            context = {
                'store_name': store.name,
                'store_owner': store.owner_name,
                'store_email': store.email,
                'store_phone': store.phone,
                'store_address': store.address,
                'area_name': store.area.name if store.area else '未設定',
                'registration_date': store.registration_date.strftime('%Y年%m月%d日 %H:%M'),
                'admin_url': f"{getattr(settings, 'ADMIN_BASE_URL', 'http://localhost:8000')}/admin/store/{store.id}/",
            }
            
            success_count = 0
            for admin_user in admin_users:
                if admin_user.email:
                    success = self._send_email(
                        template=template,
                        context=context,
                        recipient_email=admin_user.email,
                        notification=None
                    )
                    if success:
                        success_count += 1
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send store registration email: {str(e)}")
            return False
    
    def send_store_welcome_email(self, store: Store) -> bool:
        """店舗登録完了ウェルカムメールを送信"""
        try:
            template = self._get_template('store_welcome')
            if not template:
                logger.error("Store welcome template not found")
                return False
            
            context = {
                'store_name': store.name,
                'owner_name': store.owner_name,
                'area_name': store.area.name if store.area else '未設定',
                'login_url': f"{getattr(settings, 'STORE_BASE_URL', 'http://localhost:3000')}/store/login",
                'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@biid.app'),
            }
            
            return self._send_email(
                template=template,
                context=context,
                recipient_email=store.email,
                notification=None
            )
            
        except Exception as e:
            logger.error(f"Failed to send store welcome email: {str(e)}")
            return False
    
    def send_store_approval_email(self, store: Store) -> bool:
        """店舗承認通知メールを送信"""
        try:
            template = self._get_template('store_approval')
            if not template:
                logger.error("Store approval template not found")
                return False
            
            context = {
                'store_name': store.name,
                'owner_name': store.owner_name,
                'approval_date': timezone.now().strftime('%Y年%m月%d日'),
                'login_url': f"{getattr(settings, 'STORE_BASE_URL', 'http://localhost:3000')}/store/login",
                'getting_started_url': f"{getattr(settings, 'STORE_BASE_URL', 'http://localhost:3000')}/store/getting-started",
            }
            
            return self._send_email(
                template=template,
                context=context,
                recipient_email=store.email,
                notification=None
            )
            
        except Exception as e:
            logger.error(f"Failed to send store approval email: {str(e)}")
            return False
    
    def _get_template(self, template_name: str) -> Optional[EmailTemplate]:
        """テンプレートを取得"""
        try:
            return EmailTemplate.objects.get(name=template_name, is_active=True)
        except EmailTemplate.DoesNotExist:
            return None
    
    def _prepare_context(self, notification: Notification) -> Dict:
        """メールテンプレート用のコンテキストを準備"""
        base_context = {
            'user_name': notification.user.first_name or notification.user.username,
            'user_email': notification.user.email,
            'notification_title': notification.title,
            'notification_message': notification.message,
            'site_name': getattr(settings, 'SITE_NAME', 'biid Store'),
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:3000'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@biid.app'),
            'unsubscribe_url': f"{getattr(settings, 'SITE_URL', 'http://localhost:3000')}/unsubscribe/{notification.user.id}",
        }
        
        # 通知固有のコンテキストを追加
        if notification.email_context:
            base_context.update(notification.email_context)
        
        return base_context
    
    def _send_email(self, template: EmailTemplate, context: Dict, 
                   recipient_email: str, notification: Optional[Notification] = None) -> bool:
        """実際のメール送信処理"""
        email_log = None
        
        try:
            # テンプレートをレンダリング
            subject_template = Template(template.subject)
            html_template = Template(template.body_html)
            text_template = Template(template.body_text) if template.body_text else None
            
            django_context = Context(context)
            subject = subject_template.render(django_context)
            html_content = html_template.render(django_context)
            text_content = text_template.render(django_context) if text_template else None
            
            # ログエントリを作成
            email_log = EmailLog.objects.create(
                notification=notification,
                recipient_email=recipient_email,
                subject=subject,
                template_used=template.name,
                status='pending'
            )
            
            # メール送信
            if text_content:
                # HTMLとテキストの両方がある場合
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=self.from_email,
                    to=[recipient_email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send()
            else:
                # HTMLのみの場合
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=html_content,
                    from_email=self.from_email,
                    to=[recipient_email]
                )
                msg.content_subtype = "html"
                msg.send()
            
            # 送信成功をログに記録
            email_log.status = 'sent'
            email_log.sent_at = timezone.now()
            email_log.save()
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
            
            if email_log:
                email_log.status = 'failed'
                email_log.error_message = str(e)
                email_log.retry_count += 1
                email_log.save()
            
            return False
    
    def retry_failed_emails(self, max_age_hours: int = 24) -> int:
        """失敗したメールの再送信"""
        cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
        
        failed_logs = EmailLog.objects.filter(
            status='failed',
            retry_count__lt=self.max_retry_count,
            created_at__gte=cutoff_time
        ).select_related('notification')
        
        retry_count = 0
        for log in failed_logs:
            if log.notification:
                success = self.send_notification_email(log.notification)
                if success:
                    retry_count += 1
        
        return retry_count


# グローバルインスタンス
email_service = EmailService()


# === 便利関数 ===

def send_store_registration_notification(store: Store):
    """店舗登録通知を送信（管理者向け + 店舗向け）"""
    try:
        with transaction.atomic():
            # 管理者に通知
            admin_users = User.objects.filter(role='admin', is_active=True)
            email_service.send_store_registration_email(store, admin_users)
            
            # 管理者用通知レコード作成
            for admin_user in admin_users:
                Notification.objects.create(
                    user=admin_user,
                    notification_type='admin_alert',
                    title=f'新店舗登録: {store.name}',
                    message=f'{store.owner_name}さんが「{store.name}」を登録しました。承認をお待ちしています。',
                    email_template='store_registration_admin',
                    priority='high'
                )
            
            # 店舗オーナーにウェルカムメール
            email_service.send_store_welcome_email(store)
            
    except Exception as e:
        logger.error(f"Failed to send store registration notifications: {str(e)}")


def send_store_status_notification(store: Store, new_status: str):
    """店舗ステータス変更通知を送信"""
    try:
        if new_status == 'active':
            # 承認通知
            email_service.send_store_approval_email(store)
            
            # 店舗管理者アカウントがある場合は通知作成
            if hasattr(store, 'managers') and store.managers.exists():
                for manager in store.managers.all():
                    Notification.objects.create(
                        user=manager,
                        notification_type='store_approval',
                        title='店舗登録が承認されました',
                        message=f'「{store.name}」の登録が承認され、サービスをご利用いただけるようになりました。',
                        email_template='store_approval',
                        priority='high'
                    )
        
    except Exception as e:
        logger.error(f"Failed to send store status notifications: {str(e)}")