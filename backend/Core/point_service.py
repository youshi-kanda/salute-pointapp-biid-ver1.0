from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
import logging
from decimal import Decimal

from .models import User, Store, PointTransaction, UserPoint, PointTransfer, Notification

logger = logging.getLogger(__name__)


class PointService:
    """統一ポイント管理サービス"""
    
    def __init__(self):
        self.transfer_fee_rate = Decimal('0.10')  # 転送手数料率（10%）
        self.min_transfer_amount = 100  # 最小転送ポイント
        self.max_transfer_amount = 50000  # 最大転送ポイント
    
    @transaction.atomic
    def grant_points_to_user(self, user: User, points: int, store: Store = None, 
                           description: str = "", expiry_months: int = 6):
        """ユーザーにポイントを付与"""
        try:
            if points <= 0:
                raise ValidationError("付与ポイントは1以上である必要があります")
            
            # ポイント付与
            user_point = user.add_points(
                points=points,
                expiry_months=expiry_months,
                source_description=description or f"{points}ポイント付与"
            )
            
            # 店舗からの付与の場合、従量課金処理
            if store:
                charge_amount = Decimal(points) * Decimal('0.01')  # 1pt = 1円の従量課金
                store.deduct_deposit(
                    amount=charge_amount,
                    description=f"ポイント付与従量課金: {user.username}へ{points}pt"
                )
            
            logger.info(f"Points granted: {user.username} +{points}pt from {store.name if store else 'system'}")
            return user_point
            
        except Exception as e:
            logger.error(f"Failed to grant points: {str(e)}")
            raise
    
    @transaction.atomic
    def award_points(self, user: User, points: int, description: str = "", 
                    store: Store = None, reference_id: str = ""):
        """ECポイント付与専用メソッド（PointTransaction記録付き）"""
        try:
            if points <= 0:
                raise ValidationError("付与ポイントは1以上である必要があります")
            
            # ユーザーの残高を取得
            balance_before = user.point_balance
            
            # ポイント付与
            user_point = user.add_points(
                points=points,
                expiry_months=6,  # 6ヶ月有効
                source_description=description or f"EC購入ポイント付与: {points}pt"
            )
            
            # PointTransaction記録を作成
            point_transaction = PointTransaction.objects.create(
                user=user,
                store=store,
                points=points,  # 正の値で付与
                transaction_type='grant',
                description=description,
                balance_before=balance_before,
                balance_after=user.point_balance,
                reference_id=reference_id
            )
            
            # 通知作成
            Notification.objects.create(
                user=user,
                notification_type='point_received',
                title=f'{points}ポイントが付与されました',
                message=f'{store.name if store else "システム"}から{points}ポイントが付与されました。\n{description}',
                priority='normal'
            )
            
            logger.info(f"EC Points awarded: {user.username} +{points}pt from {store.name if store else 'system'}")
            return point_transaction
            
        except Exception as e:
            logger.error(f"Failed to award EC points: {str(e)}")
            raise
    
    @transaction.atomic
    def process_store_payment(self, customer: User, store: Store, points: int, 
                            description: str = "", processed_by: User = None):
        """店舗でのポイント決済処理"""
        try:
            if points <= 0:
                raise ValidationError("消費ポイントは1以上である必要があります")
            
            # ポイント消費
            consumed_points = customer.consume_points(
                points=points,
                description=description or f"店舗決済: {store.name}で{points}pt使用"
            )
            
            # 取引履歴にstore情報を追加
            latest_transaction = PointTransaction.objects.filter(
                user=customer,
                transaction_type='payment'
            ).latest('created_at')
            latest_transaction.store = store
            latest_transaction.processed_by = processed_by
            latest_transaction.save()
            
            logger.info(f"Store payment processed: {customer.username} -{points}pt at {store.name}")
            return latest_transaction
            
        except Exception as e:
            logger.error(f"Failed to process store payment: {str(e)}")
            raise
    
    @transaction.atomic
    def create_point_transfer(self, sender: User, recipient: User, points: int, 
                            message: str = ""):
        """ポイント転送リクエスト作成"""
        try:
            # バリデーション
            if points < self.min_transfer_amount:
                raise ValidationError(f"転送ポイントは{self.min_transfer_amount}pt以上である必要があります")
            
            if points > self.max_transfer_amount:
                raise ValidationError(f"転送ポイントは{self.max_transfer_amount}pt以下である必要があります")
            
            if sender == recipient:
                raise ValidationError("自分自身にはポイント転送できません")
            
            # 手数料計算
            transfer_fee = points * self.transfer_fee_rate
            total_required = points + int(transfer_fee)
            
            if sender.point_balance < total_required:
                raise ValidationError(f"ポイント残高不足です（必要: {total_required}pt, 残高: {sender.point_balance}pt）")
            
            # 転送リクエスト作成
            point_transfer = PointTransfer.objects.create(
                sender=sender,
                recipient=recipient,
                points=points,
                message=message,
                transfer_fee=transfer_fee,
                status='pending'
            )
            
            logger.info(f"Point transfer created: {sender.username} -> {recipient.username} {points}pt")
            return point_transfer
            
        except Exception as e:
            logger.error(f"Failed to create point transfer: {str(e)}")
            raise
    
    @transaction.atomic
    def execute_point_transfer(self, transfer_id: int):
        """ポイント転送実行"""
        try:
            transfer = PointTransfer.objects.get(id=transfer_id)
            result = transfer.execute_transfer()
            
            logger.info(f"Point transfer executed: {transfer.sender.username} -> {transfer.recipient.username} {transfer.points}pt")
            return result
            
        except PointTransfer.DoesNotExist:
            raise ValidationError("転送リクエストが見つかりません")
        except Exception as e:
            logger.error(f"Failed to execute point transfer: {str(e)}")
            raise
    
    def check_expired_points(self):
        """期限切れポイントをチェックして無効化"""
        try:
            expired_points = UserPoint.objects.filter(
                expiry_date__lt=timezone.now(),
                is_expired=False
            )
            
            expired_count = 0
            for user_point in expired_points:
                # 失効ポイントの取引履歴記録
                PointTransaction.objects.create(
                    user=user_point.user,
                    points=-user_point.points,
                    transaction_type='expire',
                    description=f"ポイント失効: {user_point.points}pt（期限: {user_point.expiry_date}）",
                    balance_before=user_point.user.point_balance,
                    balance_after=user_point.user.point_balance - user_point.points
                )
                
                # 失効通知
                Notification.objects.create(
                    user=user_point.user,
                    notification_type='system',
                    title='ポイントが失効しました',
                    message=f'{user_point.points}ポイントが有効期限切れで失効しました。',
                    priority='normal'
                )
                
                # ポイント無効化
                user_point.is_expired = True
                user_point.save()
                expired_count += 1
            
            logger.info(f"Expired points processed: {expired_count} point records")
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to check expired points: {str(e)}")
            raise
    
    def get_user_point_summary(self, user: User):
        """ユーザーのポイント詳細情報を取得"""
        try:
            # 有効ポイント
            valid_points = user.user_points.filter(is_expired=False)
            total_valid = valid_points.aggregate(total=Sum('points'))['total'] or 0
            
            # 近日失効予定ポイント（30日以内）
            soon_expire_date = timezone.now() + timezone.timedelta(days=30)
            soon_expire_points = valid_points.filter(
                expiry_date__lte=soon_expire_date
            ).aggregate(total=Sum('points'))['total'] or 0
            
            # 今月の取引統計
            month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_transactions = PointTransaction.objects.filter(
                user=user,
                created_at__gte=month_start
            )
            
            month_granted = month_transactions.filter(
                transaction_type__in=['grant', 'bonus'],
                points__gt=0
            ).aggregate(total=Sum('points'))['total'] or 0
            
            month_used = abs(month_transactions.filter(
                transaction_type__in=['payment', 'transfer_out'],
                points__lt=0
            ).aggregate(total=Sum('points'))['total'] or 0)
            
            return {
                'total_balance': total_valid,
                'soon_expire_points': soon_expire_points,
                'soon_expire_date': soon_expire_date,
                'current_rank': user.rank,
                'month_stats': {
                    'granted': month_granted,
                    'used': month_used,
                    'net': month_granted - month_used
                },
                'point_details': [
                    {
                        'points': up.points,
                        'expiry_date': up.expiry_date,
                        'created_at': up.created_at,
                        'days_until_expiry': (up.expiry_date - timezone.now()).days if up.expiry_date else None
                    }
                    for up in valid_points.order_by('expiry_date')
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get user point summary: {str(e)}")
            raise


# グローバルインスタンス
point_service = PointService()