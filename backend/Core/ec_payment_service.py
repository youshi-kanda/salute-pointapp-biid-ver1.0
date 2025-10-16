from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
import logging
import time
from decimal import Decimal

from .models import Store, ECPointRequest, DepositTransaction
from .fincode_service import fincode_service
from .deposit_service import deposit_service

logger = logging.getLogger(__name__)


class ECPaymentService:
    """EC購入用決済サービス"""
    
    def __init__(self):
        self.payment_timeout = 30  # 決済タイムアウト（秒）
        self.retry_attempts = 2  # 決済リトライ回数
    
    @transaction.atomic
    def process_point_purchase(self, store: Store, points_amount: int, 
                             description: str = ""):
        """ポイント購入処理（クレジット決済 → デポジット消費）"""
        try:
            # 1. まずクレジット決済を試行
            payment_result = self._attempt_credit_payment(
                store=store,
                amount=points_amount,
                description=description
            )
            
            if payment_result['success']:
                logger.info(f"Credit payment successful: Store {store.name}, Amount {points_amount}")
                return {
                    'success': True,
                    'payment_method': 'card_payment',
                    'payment_reference': payment_result['payment_id'],
                    'amount': points_amount,
                    'message': 'クレジット決済が完了しました'
                }
            
            # 2. クレジット決済失敗 → デポジットから消費
            logger.warning(f"Credit payment failed for store {store.name}: {payment_result.get('error')}")
            
            deposit_result = self._consume_from_deposit(
                store=store,
                amount=points_amount,
                description=f"{description} (クレジット決済失敗のためデポジット消費)"
            )
            
            if deposit_result['success']:
                logger.info(f"Deposit consumption successful: Store {store.name}, Amount {points_amount}")
                return {
                    'success': True,
                    'payment_method': 'deposit_consumption',
                    'payment_reference': '',
                    'deposit_transaction_id': deposit_result['transaction_id'],
                    'amount': points_amount,
                    'message': 'デポジットから消費しました'
                }
            
            # 3. 両方とも失敗
            logger.error(f"Both payment methods failed for store {store.name}")
            return {
                'success': False,
                'error': 'payment_failed',
                'message': f'決済とデポジット消費の両方が失敗しました: {deposit_result.get("error", "不明なエラー")}'
            }
            
        except Exception as e:
            logger.error(f"Point purchase processing failed: {str(e)}")
            return {
                'success': False,
                'error': 'internal_error',
                'message': f'決済処理中にエラーが発生しました: {str(e)}'
            }
    
    def _attempt_credit_payment(self, store: Store, amount: int, description: str):
        """クレジット決済を試行"""
        try:
            # 店舗の決済設定を確認
            if not self._is_credit_payment_available(store):
                return {
                    'success': False,
                    'error': 'credit_payment_not_available',
                    'message': 'クレジット決済が利用できません'
                }
            
            # FINCODE決済を実行
            payment_data = {
                'amount': amount,
                'customer_id': f"store_{store.id}",
                'order_id': f"ec_points_{store.id}_{int(timezone.now().timestamp())}",
                'description': description or f"ECポイント購入: {amount}ポイント"
            }
            
            # 複数回リトライ
            for attempt in range(self.retry_attempts):
                try:
                    result = fincode_service.process_payment(**payment_data)
                    
                    if result.get('success'):
                        return {
                            'success': True,
                            'payment_id': result.get('payment_id'),
                            'transaction_id': result.get('transaction_id'),
                            'attempt': attempt + 1
                        }
                    else:
                        logger.warning(f"Payment attempt {attempt + 1} failed: {result.get('error')}")
                        if attempt < self.retry_attempts - 1:
                            time.sleep(1)  # 1秒待機後リトライ
                
                except Exception as e:
                    logger.error(f"Payment attempt {attempt + 1} error: {str(e)}")
                    if attempt < self.retry_attempts - 1:
                        time.sleep(1)
            
            return {
                'success': False,
                'error': 'payment_failed',
                'message': f'{self.retry_attempts}回試行しましたが決済に失敗しました'
            }
            
        except Exception as e:
            logger.error(f"Credit payment attempt failed: {str(e)}")
            return {
                'success': False,
                'error': 'credit_payment_error',
                'message': str(e)
            }
    
    def _consume_from_deposit(self, store: Store, amount: int, description: str):
        """デポジットから消費"""
        try:
            # デポジット残高チェック
            if store.deposit_balance < Decimal(str(amount)):
                return {
                    'success': False,
                    'error': 'insufficient_deposit',
                    'message': f'デポジット残高が不足しています（残高: {store.deposit_balance}円, 必要: {amount}円）'
                }
            
            # デポジット消費実行
            deposit_transaction = deposit_service.consume_deposit(
                store=store,
                amount=Decimal(str(amount)),
                used_for='ec_point_purchase',
                description=description
            )
            
            return {
                'success': True,
                'transaction_id': deposit_transaction.id,
                'balance_after': store.deposit_balance
            }
            
        except ValidationError as e:
            return {
                'success': False,
                'error': 'validation_error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"Deposit consumption failed: {str(e)}")
            return {
                'success': False,
                'error': 'deposit_consumption_error',
                'message': str(e)
            }
    
    def _is_credit_payment_available(self, store: Store):
        """クレジット決済が利用可能かチェック"""
        try:
            # 店舗のステータスチェック
            if store.status != 'active':
                return False
            
            # FINCODE設定チェック
            if not getattr(settings, 'FINCODE_API_KEY', None):
                return False
            
            # 店舗固有の設定があればチェック
            # （例：店舗ごとの決済無効化フラグなど）
            if hasattr(store, 'payment_disabled') and store.payment_disabled:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Credit payment availability check failed: {str(e)}")
            return False
    
    def get_payment_history(self, store: Store, days: int = 30):
        """決済履歴を取得"""
        try:
            from django.db.models import Q
            
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            # ECポイント申請から決済履歴を取得
            payment_history = ECPointRequest.objects.filter(
                store=store,
                status__in=['approved', 'completed'],
                store_approved_at__gte=start_date
            ).values(
                'id', 'points_to_award', 'payment_method', 
                'payment_reference', 'store_approved_at'
            ).order_by('-store_approved_at')
            
            # デポジット消費履歴も取得
            deposit_history = DepositTransaction.objects.filter(
                store=store,
                transaction_type='consumption',
                created_at__gte=start_date
            ).values(
                'id', 'amount', 'description', 'created_at'
            ).order_by('-created_at')
            
            # 統計情報
            stats = self._calculate_payment_stats(store, start_date)
            
            return {
                'success': True,
                'payment_history': list(payment_history),
                'deposit_history': list(deposit_history),
                'stats': stats,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Failed to get payment history: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_payment_stats(self, store: Store, start_date):
        """決済統計を計算"""
        try:
            from django.db.models import Sum, Count
            
            # ECポイント申請の統計
            ec_stats = ECPointRequest.objects.filter(
                store=store,
                status__in=['approved', 'completed'],
                store_approved_at__gte=start_date
            ).aggregate(
                total_requests=Count('id'),
                total_points=Sum('points_to_award'),
                credit_payments=Count('id', filter=Q(payment_method='card_payment')),
                deposit_payments=Count('id', filter=Q(payment_method='deposit_consumption'))
            )
            
            # デポジット消費の統計
            deposit_stats = DepositTransaction.objects.filter(
                store=store,
                transaction_type='consumption',
                used_for='ec_point_purchase',
                created_at__gte=start_date
            ).aggregate(
                total_amount=Sum('amount'),
                total_transactions=Count('id')
            )
            
            return {
                'ec_requests': {
                    'total': ec_stats['total_requests'] or 0,
                    'total_points': ec_stats['total_points'] or 0,
                    'credit_payments': ec_stats['credit_payments'] or 0,
                    'deposit_payments': ec_stats['deposit_payments'] or 0
                },
                'deposit_consumption': {
                    'total_amount': float(deposit_stats['total_amount'] or 0),
                    'total_transactions': deposit_stats['total_transactions'] or 0
                },
                'payment_method_ratio': {
                    'credit': ec_stats['credit_payments'] or 0,
                    'deposit': ec_stats['deposit_payments'] or 0
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate payment stats: {str(e)}")
            return {}
    
    def check_store_payment_health(self, store: Store):
        """店舗の決済状況をヘルスチェック"""
        try:
            health_status = {
                'overall': 'healthy',
                'issues': [],
                'recommendations': []
            }
            
            # 1. デポジット残高チェック
            if store.deposit_balance < Decimal('10000'):  # 1万円未満
                health_status['issues'].append('デポジット残高が少なくなっています')
                health_status['recommendations'].append('デポジットのチャージを検討してください')
                if store.deposit_balance < Decimal('5000'):  # 5千円未満
                    health_status['overall'] = 'warning'
            
            # 2. 最近の決済失敗率チェック
            recent_requests = ECPointRequest.objects.filter(
                store=store,
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            )
            
            if recent_requests.exists():
                failed_requests = recent_requests.filter(status='failed').count()
                total_requests = recent_requests.count()
                failure_rate = (failed_requests / total_requests) * 100
                
                if failure_rate > 20:  # 20%以上失敗
                    health_status['issues'].append(f'最近の決済失敗率が高くなっています（{failure_rate:.1f}%）')
                    health_status['recommendations'].append('決済設定を確認してください')
                    health_status['overall'] = 'warning'
            
            # 3. 自動チャージ設定チェック
            try:
                auto_charge_rule = store.auto_charge_rule
                if not auto_charge_rule.is_enabled:
                    health_status['recommendations'].append('自動チャージを有効にすることをお勧めします')
            except:
                health_status['recommendations'].append('自動チャージの設定をお勧めします')
            
            # 4. 総合判定
            if len(health_status['issues']) > 2:
                health_status['overall'] = 'critical'
            elif len(health_status['issues']) > 0:
                health_status['overall'] = 'warning'
            
            return {
                'success': True,
                'health': health_status,
                'current_balance': float(store.deposit_balance),
                'last_check': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# グローバルインスタンス
ec_payment_service = ECPaymentService()