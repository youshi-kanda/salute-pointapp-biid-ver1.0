# FINCODE決済サービス

from django.conf import settings
from typing import Dict, Any, Optional
import logging
from .fincode_service import fincode_service, FINCODEError

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """決済ゲートウェイエラー"""
    def __init__(self, message: str, error_code: str = None, gateway: str = None):
        super().__init__(message)
        self.error_code = error_code
        self.gateway = gateway


class PaymentGatewayService:
    """FINCODE決済サービス"""
    
    def __init__(self):
        """FINCODE決済サービスを初期化"""
        self.gateway = "fincode"
        self.service = fincode_service
        logger.info("PaymentGatewayService initialized with FINCODE")

    def initiate_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """決済開始"""
        try:
            logger.info(f"🔄 Initiating FINCODE payment: {payment_data.get('order_id')}")
            result = self.service.initiate_payment(payment_data)
            return self._normalize_payment_response(result)
            
        except FINCODEError as e:
            logger.error(f"❌ FINCODE payment error: {str(e)}")
            raise PaymentGatewayError(
                str(e), 
                error_code=getattr(e, 'error_code', None),
                gateway=self.gateway
            )
        except Exception as e:
            logger.error(f"❌ Payment error: {str(e)}")
            raise PaymentGatewayError(f"Payment initiation failed: {str(e)}", gateway=self.gateway)

    def check_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """決済ステータス確認"""
        try:
            logger.info(f"🔍 Checking FINCODE payment status: {transaction_id}")
            result = self.service.check_payment_status(transaction_id)
            return self._normalize_status_response(result)
            
        except FINCODEError as e:
            logger.error(f"❌ FINCODE status check error: {str(e)}")
            raise PaymentGatewayError(
                str(e),
                error_code=getattr(e, 'error_code', None),
                gateway=self.gateway
            )
        except Exception as e:
            logger.error(f"❌ Status check error: {str(e)}")
            raise PaymentGatewayError(f"Status check failed: {str(e)}", gateway=self.gateway)

    def refund_payment(self, transaction_id: str, amount: Optional[int] = None, reason: str = '') -> Dict[str, Any]:
        """返金処理"""
        try:
            logger.info(f"💸 Processing FINCODE refund: {transaction_id}")
            result = self.service.refund_payment(transaction_id, amount, reason)
            return self._normalize_refund_response(result)
            
        except FINCODEError as e:
            logger.error(f"❌ FINCODE refund error: {str(e)}")
            raise PaymentGatewayError(
                str(e),
                error_code=getattr(e, 'error_code', None),
                gateway=self.gateway
            )
        except Exception as e:
            logger.error(f"❌ Refund error: {str(e)}")
            raise PaymentGatewayError(f"Refund failed: {str(e)}", gateway=self.gateway)

    def _normalize_payment_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """決済開始レスポンスの正規化"""
        return {
            'success': result.get('success', False),
            'payment_id': result.get('payment_id'),
            'order_id': result.get('order_id'),
            'redirect_url': result.get('redirect_url'),
            'status': result.get('status', 'pending'),
            'gateway': 'fincode',
            'db_transaction_id': result.get('db_transaction_id'),
            'original_response': result
        }

    def _normalize_status_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """ステータス確認レスポンスの正規化"""
        return {
            'success': result.get('success', False),
            'status': result.get('status', 'failed'),
            'payment_id': result.get('payment_id'),
            'order_id': result.get('order_id'),
            'amount': result.get('amount'),
            'payment_method': result.get('payment_method'),
            'completed_at': result.get('completed_at'),
            'updated_at': result.get('updated_at'),
            'gateway': 'fincode',
            'original_response': result
        }

    def _normalize_refund_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """返金レスポンスの正規化"""
        return {
            'success': result.get('success', False),
            'refund_id': result.get('refund_id'),
            'refund_amount': result.get('refund_amount'),
            'status': result.get('status', 'failed'),
            'gateway': 'fincode',
            'original_response': result
        }

    @property
    def gateway_name(self) -> str:
        """決済ゲートウェイ名を取得"""
        return "fincode"

    @property
    def is_mock_mode(self) -> bool:
        """モックモードかどうかを確認"""
        return getattr(settings, 'FINCODE_MOCK', False)


# デフォルトインスタンス
payment_gateway_service = PaymentGatewayService()