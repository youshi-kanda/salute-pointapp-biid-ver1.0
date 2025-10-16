# GMO FINCODE 決済サービス

import requests
import json
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .models import User, PaymentTransaction

logger = logging.getLogger(__name__)

class FINCODEError(Exception):
    """FINCODE API エラー"""
    def __init__(self, message: str, error_code: str = None, status_code: int = None):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code

class FINCODEService:
    """GMO FINCODE 決済サービス"""
    
    def __init__(self):
        # FINCODE設定（本番環境対応）
        from decouple import config
        self.api_key = config('FINCODE_API_KEY', default='')
        self.secret_key = config('FINCODE_SECRET_KEY', default='')
        self.shop_id = config('FINCODE_SHOP_ID', default='')
        self.api_base_url = config('FINCODE_BASE_URL', default='https://api.fincode.jp')
        self.is_production = config('FINCODE_IS_PRODUCTION', default=False, cast=bool)
        self.timeout = config('FINCODE_TIMEOUT', default=30, cast=int)
        
        # 本番環境でのAPI設定検証
        if self.is_production:
            if not all([self.api_key, self.secret_key, self.shop_id]):
                raise FINCODEError("本番環境でFINCODE認証情報が不足しています")
            logger.info("FINCODE本番環境モードで初期化されました")
        else:
            logger.info("FINCODEテスト環境モードで初期化されました")
        
        # 決済方法マッピング（FINCODE仕様に合わせて更新予定）
        self.payment_method_map = {
            'paypay': 'paypay',
            'card': 'card',
            'applepay': 'applepay', 
            'googlepay': 'googlepay',
            'konbini': 'konbini',
            'bank_transfer': 'bank_transfer',
            'virtual_account': 'virtual_account'
        }
        
        # ステータスマッピング（FINCODE仕様に合わせて更新予定）
        self.status_map = {
            'UNPROCESSED': 'pending',
            'AUTHORIZED': 'processing', 
            'CAPTURED': 'completed',
            'CANCELED': 'cancelled',
            'FAILED': 'failed'
        }

    def initiate_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """決済開始"""
        try:
            logger.info(f"🔄 Initiating FINCODE payment: {payment_data.get('order_id')}")
            
            # リクエストデータ構築
            request_data = self._build_payment_request(payment_data)
            
            # 本番環境とテスト環境の処理分岐
            if self.is_production:
                response_data = self._call_fincode_api('/v1/payments', request_data, method='POST')
            else:
                # 開発環境ではモックレスポンス
                response_data = self._mock_fincode_response('payment', request_data)
            
            # レスポンス処理
            if response_data.get('status') in ['UNPROCESSED', 'AUTHORIZED']:
                # トランザクション記録
                transaction = self._create_transaction_record(payment_data, response_data)
                
                return {
                    'success': True,
                    'payment_id': response_data.get('id'),
                    'redirect_url': response_data.get('redirect_url'),
                    'order_id': payment_data['order_id'],
                    'status': self.status_map.get(response_data.get('status'), 'pending'),
                    'db_transaction_id': transaction.id if transaction else None
                }
            else:
                raise FINCODEError(
                    response_data.get('error_message', '決済の開始に失敗しました'),
                    response_data.get('error_code'),
                    response_data.get('status_code')
                )
                
        except FINCODEError:
            raise
        except Exception as e:
            logger.error(f"FINCODE payment initiation failed: {str(e)}")
            raise FINCODEError(f"決済処理でシステムエラーが発生しました: {str(e)}")

    def check_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """決済ステータス確認"""
        try:
            logger.info(f"🔍 Checking FINCODE payment status: {payment_id}")
            
            # キャッシュから確認
            cache_key = f"fincode_status_{payment_id}"
            cached_status = cache.get(cache_key)
            if cached_status and cached_status.get('status') == 'completed':
                return cached_status
            
            if self.is_production:
                response_data = self._call_fincode_api(f'/v1/payments/{payment_id}')
            else:
                response_data = self._mock_fincode_response('status', {'payment_id': payment_id})
            
            status_result = {
                'success': True,
                'status': self.status_map.get(response_data.get('status'), 'failed'),
                'payment_id': payment_id,
                'order_id': response_data.get('order_id'),
                'amount': response_data.get('amount'),
                'payment_method': response_data.get('pay_type'),
                'completed_at': response_data.get('created'),
                'updated_at': response_data.get('updated')
            }
            
            # 完了ステータスの場合はキャッシュ（24時間）
            if status_result['status'] == 'completed':
                cache.set(cache_key, status_result, 86400)
                
                # DBのトランザクション更新
                self._update_transaction_status(payment_id, 'completed', response_data)
            
            return status_result
            
        except Exception as e:
            logger.error(f"FINCODE status check failed: {str(e)}")
            return {
                'success': False,
                'status': 'failed',
                'error_message': str(e)
            }

    def refund_payment(self, payment_id: str, amount: Optional[int] = None, reason: str = '') -> Dict[str, Any]:
        """返金処理"""
        try:
            logger.info(f"💸 FINCODE refund request: {payment_id}, amount: {amount}")
            
            request_data = {
                'reason': reason
            }
            
            if amount is not None:
                request_data['amount'] = amount
            
            if self.is_production:
                response_data = self._call_fincode_api(f'/v1/payments/{payment_id}/refund', request_data, method='POST')
            else:
                response_data = self._mock_fincode_response('refund', request_data)
            
            if response_data.get('status') == 'REFUNDED':
                # 返金記録
                self._create_refund_record(payment_id, response_data)
                
                return {
                    'success': True,
                    'refund_id': response_data.get('id'),
                    'refund_amount': response_data.get('amount', amount),
                    'status': 'completed'
                }
            else:
                raise FINCODEError(
                    response_data.get('error_message', '返金処理に失敗しました'),
                    response_data.get('error_code')
                )
                
        except FINCODEError:
            raise
        except Exception as e:
            logger.error(f"FINCODE refund failed: {str(e)}")
            raise FINCODEError(f"返金処理でシステムエラーが発生しました: {str(e)}")

    def _build_payment_request(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """決済リクエストデータ構築"""
        pay_type = self.payment_method_map.get(payment_data.get('payment_method'), 'card')
        
        # FINCODE API仕様に合わせて構築（API仕様提供後に詳細更新）
        return {
            'order_id': payment_data['order_id'],
            'amount': payment_data['amount'],
            'currency': payment_data.get('currency', 'JPY'),
            'pay_type': pay_type,
            'customer_id': payment_data.get('customer_id'),
            'customer_name': payment_data.get('customer_name'),
            'customer_email': payment_data.get('customer_email'),
            'description': payment_data.get('description', 'BIID Point App Payment'),
            'success_url': payment_data.get('return_url'),
            'cancel_url': payment_data.get('cancel_url'),
            'webhook_url': payment_data.get('notify_url'),
            'metadata': payment_data.get('metadata', {})
        }

    def _call_fincode_api(self, endpoint: str, data: Dict[str, Any] = None, method: str = 'GET') -> Dict[str, Any]:
        """FINCODE API呼び出し"""
        url = f"{self.api_base_url}{endpoint}"
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'BIID-PointApp/1.0'
        }
        
        # API仕様に基づく認証（Bearer Token）
        # 現在のテストAPIキーでは401エラーが返るが、これは正常な応答
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=self.timeout)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FINCODE API call failed: {url}, error: {str(e)}")
            raise FINCODEError(f"FINCODE APIエラー: {str(e)}")

    def _mock_fincode_response(self, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """開発用モックレスポンス"""
        import time
        import random
        
        # 処理時間シミュレート
        time.sleep(random.uniform(0.5, 2.0))
        
        if operation == 'payment':
            order_id = data.get('order_id')
            amount = data.get('amount', 0)
            
            return {
                'id': f'FINCODE_{int(time.time())}_{random.randint(1000, 9999)}',
                'order_id': order_id,
                'amount': amount,
                'status': 'UNPROCESSED',
                'pay_type': data.get('pay_type', 'card'),
                'redirect_url': f'http://127.0.0.1:8000/api/fincode/mock-payment/{order_id}/?amount={amount}',
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }
        
        elif operation == 'status':
            # 80%の確率で完了
            is_completed = random.random() < 0.8
            status = 'CAPTURED' if is_completed else 'AUTHORIZED'
            
            return {
                'id': data.get('payment_id'),
                'order_id': f'ORDER_{int(time.time())}',
                'amount': 30000,
                'status': status,
                'pay_type': 'card',
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }
        
        elif operation == 'refund':
            return {
                'id': f'REFUND_{int(time.time())}',
                'amount': data.get('amount', 1000),
                'status': 'REFUNDED',
                'created': datetime.now().isoformat()
            }
        
        return {'status': 'FAILED', 'error_message': 'Unknown operation'}

    def _create_transaction_record(self, payment_data: Dict[str, Any], response_data: Dict[str, Any]) -> Optional['PaymentTransaction']:
        """トランザクション記録作成"""
        try:
            customer_id = payment_data.get('customer_id')
            if not customer_id:
                return None
                
            customer = User.objects.filter(member_id=customer_id).first()
            if not customer:
                logger.warning(f"Customer not found: {customer_id}")
                return None
            
            transaction = PaymentTransaction.objects.create(
                user=customer,
                transaction_type='payment',
                payment_method='fincode',
                amount=payment_data['amount'],
                points_earned=payment_data.get('points_earned', 0),
                points_used=payment_data.get('points_used', 0),
                status='pending',
                external_transaction_id=response_data.get('id'),
                order_id=payment_data['order_id'],
                terminal_id=payment_data.get('terminal_id'),
                store_id=payment_data.get('store_id'),
                metadata={
                    'fincode_response': response_data,
                    'payment_method_detail': payment_data.get('payment_method'),
                    'redirect_url': response_data.get('redirect_url'),
                }
            )
            
            logger.info(f"Transaction record created: {transaction.id}")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to create transaction record: {str(e)}")
            return None

    def _update_transaction_status(self, payment_id: str, status: str, response_data: Dict[str, Any]):
        """トランザクションステータス更新"""
        try:
            transaction = PaymentTransaction.objects.filter(
                external_transaction_id=payment_id
            ).first()
            
            if transaction:
                transaction.status = status
                if status == 'completed':
                    transaction.completed_at = timezone.now()
                    
                    # メタデータ更新
                    if transaction.metadata:
                        transaction.metadata.update({
                            'completion_response': response_data,
                            'completed_at': response_data.get('updated')
                        })
                    
                transaction.save()
                logger.info(f"Transaction status updated: {transaction.id} -> {status}")
            
        except Exception as e:
            logger.error(f"Failed to update transaction status: {str(e)}")

    def _create_refund_record(self, payment_id: str, response_data: Dict[str, Any]):
        """返金記録作成"""
        try:
            # 元のトランザクション検索
            original_transaction = PaymentTransaction.objects.filter(
                external_transaction_id=payment_id
            ).first()
            
            if original_transaction:
                # 返金記録作成
                refund_transaction = PaymentTransaction.objects.create(
                    user=original_transaction.user,
                    transaction_type='refund',
                    payment_method='fincode',
                    amount=-response_data.get('amount', 0),
                    status='completed',
                    external_transaction_id=response_data.get('id'),
                    related_transaction=original_transaction,
                    terminal_id=original_transaction.terminal_id,
                    store_id=original_transaction.store_id,
                    metadata={
                        'fincode_refund_response': response_data,
                        'original_payment_id': payment_id
                    },
                    completed_at=timezone.now()
                )
                
                logger.info(f"Refund record created: {refund_transaction.id}")
                return refund_transaction
            
        except Exception as e:
            logger.error(f"Failed to create refund record: {str(e)}")
            return None


# サービスインスタンス
fincode_service = FINCODEService()