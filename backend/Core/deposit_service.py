from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple

from .models import Store, DepositTransaction, DepositAutoChargeRule, DepositUsageLog, Notification
from .email_service import email_service

logger = logging.getLogger(__name__)


class DepositService:
    """デポジット管理サービス"""
    
    def __init__(self):
        self.min_charge_amount = Decimal('1000')  # 最小チャージ金額
        self.max_charge_amount = Decimal('1000000')  # 最大チャージ金額
        self.charge_fee_rate = Decimal('0.03')  # チャージ手数料率（3%）
    
    @transaction.atomic
    def charge_deposit(self, store: Store, amount: Decimal, payment_method: str, 
                      payment_reference: str = '', description: str = '') -> DepositTransaction:
        """デポジットチャージ"""
        try:
            # バリデーション
            if amount < self.min_charge_amount:
                raise ValidationError(f"チャージ金額は{self.min_charge_amount}円以上である必要があります")
            
            if amount > self.max_charge_amount:
                raise ValidationError(f"チャージ金額は{self.max_charge_amount}円以下である必要があります")
            
            # 手数料計算
            fee_amount = amount * self.charge_fee_rate
            net_amount = amount - fee_amount
            
            # 取引記録作成
            deposit_transaction = DepositTransaction()
            deposit_transaction.store = store
            deposit_transaction.transaction_id = deposit_transaction.generate_transaction_id()
            deposit_transaction.transaction_type = 'charge'
            deposit_transaction.amount = net_amount
            deposit_transaction.balance_before = store.deposit_balance
            deposit_transaction.balance_after = store.deposit_balance + net_amount
            deposit_transaction.payment_method = payment_method
            deposit_transaction.payment_reference = payment_reference
            deposit_transaction.fee_amount = fee_amount
            deposit_transaction.fee_rate = self.charge_fee_rate * 100  # パーセンテージ
            deposit_transaction.description = description or f"デポジットチャージ（{payment_method}）"
            deposit_transaction.status = 'completed'
            deposit_transaction.processed_at = timezone.now()
            deposit_transaction.save()
            
            # 店舗の残高更新
            store.deposit_balance += net_amount
            store.save()
            
            # 通知作成
            self._create_charge_notification(store, deposit_transaction)
            
            logger.info(f"Deposit charged: {store.name} - {net_amount}円 (手数料: {fee_amount}円)")
            return deposit_transaction
            
        except Exception as e:
            logger.error(f"Failed to charge deposit: {str(e)}")
            raise
    
    @transaction.atomic
    def consume_deposit(self, store: Store, amount: Decimal, used_for: str, 
                       description: str = '', related_promotion=None, user_count: int = 0) -> DepositTransaction:
        """デポジット消費"""
        try:
            # 残高チェック
            if store.deposit_balance < amount:
                raise ValidationError(f"デポジット残高が不足しています（残高: {store.deposit_balance}円, 必要額: {amount}円）")
            
            # 取引記録作成
            deposit_transaction = DepositTransaction()
            deposit_transaction.store = store
            deposit_transaction.transaction_id = deposit_transaction.generate_transaction_id()
            deposit_transaction.transaction_type = 'consumption'
            deposit_transaction.amount = amount
            deposit_transaction.balance_before = store.deposit_balance
            deposit_transaction.balance_after = store.deposit_balance - amount
            deposit_transaction.payment_method = 'system'
            deposit_transaction.description = description or f"デポジット消費（{used_for}）"
            deposit_transaction.status = 'completed'
            deposit_transaction.processed_at = timezone.now()
            deposit_transaction.save()
            
            # 使用履歴作成
            usage_log = DepositUsageLog.objects.create(
                store=store,
                transaction=deposit_transaction,
                used_for=used_for,
                used_amount=amount,
                related_promotion=related_promotion,
                user_count=user_count
            )
            
            # 店舗の残高更新
            store.deposit_balance -= amount
            store.save()
            
            # 自動チャージチェック
            self._check_auto_charge(store)
            
            logger.info(f"Deposit consumed: {store.name} - {amount}円 for {used_for}")
            return deposit_transaction
            
        except Exception as e:
            logger.error(f"Failed to consume deposit: {str(e)}")
            raise
    
    def setup_auto_charge(self, store: Store, trigger_amount: Decimal, charge_amount: Decimal,
                         payment_method: str, payment_reference: str = '',
                         max_charge_per_day: Optional[Decimal] = None,
                         max_charge_per_month: Optional[Decimal] = None,
                         notification_email: str = '') -> DepositAutoChargeRule:
        """自動チャージ設定"""
        try:
            # バリデーション
            if charge_amount < self.min_charge_amount:
                raise ValidationError(f"チャージ金額は{self.min_charge_amount}円以上である必要があります")
            
            if trigger_amount < 0:
                raise ValidationError("トリガー金額は0円以上である必要があります")
            
            # 既存設定を取得または作成
            auto_charge_rule, created = DepositAutoChargeRule.objects.get_or_create(
                store=store,
                defaults={
                    'trigger_amount': trigger_amount,
                    'charge_amount': charge_amount,
                    'payment_method': payment_method,
                    'payment_reference': payment_reference,
                    'max_charge_per_day': max_charge_per_day,
                    'max_charge_per_month': max_charge_per_month,
                    'notification_email': notification_email or store.email,
                    'is_enabled': True
                }
            )
            
            if not created:
                # 既存設定を更新
                auto_charge_rule.trigger_amount = trigger_amount
                auto_charge_rule.charge_amount = charge_amount
                auto_charge_rule.payment_method = payment_method
                auto_charge_rule.payment_reference = payment_reference
                auto_charge_rule.max_charge_per_day = max_charge_per_day
                auto_charge_rule.max_charge_per_month = max_charge_per_month
                auto_charge_rule.notification_email = notification_email or store.email
                auto_charge_rule.is_enabled = True
                auto_charge_rule.save()
            
            logger.info(f"Auto charge rule set up: {store.name}")
            return auto_charge_rule
            
        except Exception as e:
            logger.error(f"Failed to setup auto charge: {str(e)}")
            raise
    
    def _check_auto_charge(self, store: Store):
        """自動チャージの実行チェック"""
        try:
            # 自動チャージ設定を取得
            try:
                auto_charge_rule = store.auto_charge_rule
            except DepositAutoChargeRule.DoesNotExist:
                return
            
            # 自動チャージが無効の場合は何もしない
            if not auto_charge_rule.is_enabled:
                return
            
            # トリガー条件チェック
            if store.deposit_balance >= auto_charge_rule.trigger_amount:
                return
            
            # 制限チェック
            if not auto_charge_rule.can_trigger_today():
                logger.warning(f"Auto charge daily limit exceeded: {store.name}")
                return
            
            if not auto_charge_rule.can_trigger_this_month():
                logger.warning(f"Auto charge monthly limit exceeded: {store.name}")
                return
            
            # 自動チャージ実行
            self._execute_auto_charge(store, auto_charge_rule)
            
        except Exception as e:
            logger.error(f"Failed to check auto charge: {str(e)}")
    
    @transaction.atomic
    def _execute_auto_charge(self, store: Store, auto_charge_rule: DepositAutoChargeRule):
        """自動チャージ実行"""
        try:
            # 手数料計算
            fee_amount = auto_charge_rule.charge_amount * self.charge_fee_rate
            net_amount = auto_charge_rule.charge_amount - fee_amount
            
            # 取引記録作成
            deposit_transaction = DepositTransaction()
            deposit_transaction.store = store
            deposit_transaction.transaction_id = deposit_transaction.generate_transaction_id()
            deposit_transaction.transaction_type = 'auto_charge'
            deposit_transaction.amount = net_amount
            deposit_transaction.balance_before = store.deposit_balance
            deposit_transaction.balance_after = store.deposit_balance + net_amount
            deposit_transaction.payment_method = auto_charge_rule.payment_method
            deposit_transaction.payment_reference = auto_charge_rule.payment_reference
            deposit_transaction.fee_amount = fee_amount
            deposit_transaction.fee_rate = self.charge_fee_rate * 100
            deposit_transaction.description = f"自動チャージ（残高: {store.deposit_balance}円 → トリガー: {auto_charge_rule.trigger_amount}円）"
            deposit_transaction.status = 'completed'
            deposit_transaction.processed_at = timezone.now()
            deposit_transaction.save()
            
            # 店舗の残高更新
            store.deposit_balance += net_amount
            store.save()
            
            # 自動チャージルールの最終実行日時更新
            auto_charge_rule.last_triggered_at = timezone.now()
            auto_charge_rule.save()
            
            # 通知作成
            self._create_auto_charge_notification(store, deposit_transaction, auto_charge_rule)
            
            logger.info(f"Auto charge executed: {store.name} - {net_amount}円")
            
        except Exception as e:
            logger.error(f"Failed to execute auto charge: {str(e)}")
            raise
    
    def get_deposit_balance(self, store: Store) -> Dict:
        """デポジット残高情報を取得"""
        try:
            # 最近の取引履歴
            recent_transactions = DepositTransaction.objects.filter(
                store=store
            ).order_by('-created_at')[:10]
            
            # 今月の使用統計
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            from django.db import models
            
            month_stats = DepositTransaction.objects.filter(
                store=store,
                created_at__gte=month_start,
                status='completed'
            ).aggregate(
                total_charge=models.Sum('amount', filter=models.Q(transaction_type__in=['charge', 'auto_charge'])),
                total_consumption=models.Sum('amount', filter=models.Q(transaction_type='consumption')),
                total_fee=models.Sum('fee_amount')
            )
            
            # 自動チャージ設定
            auto_charge_info = None
            try:
                auto_charge_rule = store.auto_charge_rule
                auto_charge_info = {
                    'is_enabled': auto_charge_rule.is_enabled,
                    'trigger_amount': auto_charge_rule.trigger_amount,
                    'charge_amount': auto_charge_rule.charge_amount,
                    'payment_method': auto_charge_rule.payment_method,
                    'last_triggered_at': auto_charge_rule.last_triggered_at
                }
            except DepositAutoChargeRule.DoesNotExist:
                pass
            
            return {
                'current_balance': store.deposit_balance,
                'recent_transactions': [
                    {
                        'id': t.id,
                        'transaction_type': t.transaction_type,
                        'amount': t.amount,
                        'description': t.description,
                        'status': t.status,
                        'created_at': t.created_at
                    } for t in recent_transactions
                ],
                'month_stats': {
                    'total_charge': month_stats['total_charge'] or 0,
                    'total_consumption': month_stats['total_consumption'] or 0,
                    'total_fee': month_stats['total_fee'] or 0,
                    'net_change': (month_stats['total_charge'] or 0) - (month_stats['total_consumption'] or 0)
                },
                'auto_charge_info': auto_charge_info
            }
            
        except Exception as e:
            logger.error(f"Failed to get deposit balance: {str(e)}")
            raise
    
    def _create_charge_notification(self, store: Store, transaction: DepositTransaction):
        """チャージ通知作成"""
        try:
            if hasattr(store, 'managers') and store.managers.exists():
                for manager in store.managers.all():
                    Notification.objects.create(
                        user=manager,
                        notification_type='system',
                        title='デポジットチャージ完了',
                        message=f'デポジットに{transaction.amount}円をチャージしました。（手数料: {transaction.fee_amount}円）',
                        priority='normal'
                    )
        except Exception as e:
            logger.error(f"Failed to create charge notification: {str(e)}")
    
    def _create_auto_charge_notification(self, store: Store, transaction: DepositTransaction, 
                                       auto_charge_rule: DepositAutoChargeRule):
        """自動チャージ通知作成"""
        try:
            if hasattr(store, 'managers') and store.managers.exists():
                for manager in store.managers.all():
                    Notification.objects.create(
                        user=manager,
                        notification_type='system',
                        title='自動チャージ実行',
                        message=f'デポジット残高が{auto_charge_rule.trigger_amount}円を下回ったため、自動的に{transaction.amount}円をチャージしました。',
                        priority='high'
                    )
        except Exception as e:
            logger.error(f"Failed to create auto charge notification: {str(e)}")


# グローバルインスタンス
deposit_service = DepositService()