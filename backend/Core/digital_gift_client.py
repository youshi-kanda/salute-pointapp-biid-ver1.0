import requests
import pyotp
import time
import json
import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import (
    DigitalGiftBrand, DigitalGiftPurchaseID, DigitalGiftPurchase, 
    DigitalGiftUsageLog, APIAccessKey
)

logger = logging.getLogger(__name__)


class DigitalGiftAPIError(Exception):
    """デジタルギフトAPI エラー"""
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(message)


class DigitalGiftAPIClient:
    """デジタルギフトAPI クライアント"""
    
    def __init__(self, access_key: APIAccessKey):
        self.access_key = access_key
        self.base_url = getattr(settings, 'DIGITAL_GIFT_API_BASE_URL', 'https://api.realpay.jp/v1')
        self.timeout = getattr(settings, 'DIGITAL_GIFT_API_TIMEOUT', 30)
        self.session = requests.Session()
        
        # デフォルトヘッダー設定
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PointApp-BIID/1.0',
            'X-RealPay-Gift-API-Access-Key': self.access_key.key
        })
    
    def _generate_totp_token(self) -> str:
        """TOTP認証トークンを生成"""
        try:
            totp = pyotp.TOTP(
                self.access_key.shared_secret,
                interval=self.access_key.time_step,
                digits=self.access_key.totp_digits
            )
            return totp.now()
        except Exception as e:
            logger.error(f"TOTP token generation failed: {e}")
            raise DigitalGiftAPIError(f"Authentication token generation failed: {e}")
    
    def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """APIリクエストを実行"""
        url = f"{self.base_url}{endpoint}"
        
        # TOTP認証ヘッダーを追加
        headers = {
            'X-RealPay-Gift-API-Access-Token': self._generate_totp_token()
        }
        
        try:
            logger.info(f"Making {method} request to {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            logger.info(f"Response: {response.status_code}")
            
            # レスポンス処理
            if response.status_code == 200:
                return response.json()
            
            # エラーレスポンス処理
            try:
                error_data = response.json()
            except:
                error_data = {'message': response.text}
            
            raise DigitalGiftAPIError(
                message=error_data.get('message', f'API request failed with status {response.status_code}'),
                status_code=response.status_code,
                response_data=error_data
            )
            
        except requests.exceptions.Timeout:
            raise DigitalGiftAPIError("API request timeout")
        except requests.exceptions.ConnectionError:
            raise DigitalGiftAPIError("API connection error")
        except DigitalGiftAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected API error: {e}")
            raise DigitalGiftAPIError(f"Unexpected error: {e}")
    
    def get_brands(self) -> List[Dict[str, Any]]:
        """利用可能なギフトブランド一覧を取得"""
        try:
            response = self._make_request('GET', '/gifts/brands')
            brands_data = response.get('brands', [])
            
            # データベースに同期
            self._sync_brands_to_db(brands_data)
            
            return brands_data
            
        except Exception as e:
            logger.error(f"Failed to fetch brands: {e}")
            raise
    
    def _sync_brands_to_db(self, brands_data: List[Dict]) -> None:
        """ブランドデータをデータベースに同期"""
        for brand_data in brands_data:
            brand_code = brand_data.get('code')
            if not brand_code:
                continue
            
            brand, created = DigitalGiftBrand.objects.update_or_create(
                brand_code=brand_code,
                defaults={
                    'brand_name': brand_data.get('name', ''),
                    'brand_name_en': brand_data.get('name_en', ''),
                    'description': brand_data.get('description', ''),
                    'logo_url': brand_data.get('logo_url', ''),
                    'supported_prices': brand_data.get('supported_prices', []),
                    'min_price': brand_data.get('min_price', 0),
                    'max_price': brand_data.get('max_price', 0),
                    'commission_rate': Decimal(str(brand_data.get('commission_rate', 0))),
                    'commission_tax_rate': Decimal(str(brand_data.get('commission_tax_rate', 0))),
                    'is_active': brand_data.get('is_active', True),
                    'last_synced': timezone.now()
                }
            )
            
            if created:
                logger.info(f"Created new brand: {brand.brand_name}")
            else:
                logger.info(f"Updated brand: {brand.brand_name}")
    
    def create_purchase_id(self, brand_code: str, price: int, 
                          design_code: str = 'default', video_message: str = '', 
                          advertising_text: str = '') -> Dict[str, Any]:
        """購入IDを作成"""
        try:
            # ブランド存在確認
            brand = DigitalGiftBrand.objects.get(brand_code=brand_code, is_active=True)
            
            # 価格検証
            if brand.supported_prices and price not in brand.supported_prices:
                raise DigitalGiftAPIError(f"Unsupported price {price} for brand {brand_code}")
            
            if price < brand.min_price or price > brand.max_price:
                raise DigitalGiftAPIError(f"Price {price} out of range for brand {brand_code}")
            
            # API リクエスト
            request_data = {
                'brand_code': brand_code,
                'price': price,
                'design_code': design_code,
                'video_message': video_message,
                'advertising_text': advertising_text
            }
            
            response = self._make_request('POST', '/gifts/purchase-id', data=request_data)
            
            # データベースに保存
            purchase_id_obj = DigitalGiftPurchaseID.objects.create(
                brand=brand,
                purchase_id=response['purchase_id'],
                price=price,
                design_code=design_code,
                video_message=video_message,
                advertising_text=advertising_text,
                expires_at=timezone.now() + timezone.timedelta(minutes=30),  # 30分有効
                api_response=response
            )
            
            logger.info(f"Created purchase ID: {response['purchase_id']} for brand {brand_code}")
            
            return response
            
        except DigitalGiftBrand.DoesNotExist:
            raise DigitalGiftAPIError(f"Brand {brand_code} not found or inactive")
        except Exception as e:
            logger.error(f"Failed to create purchase ID: {e}")
            raise
    
    def purchase_gift(self, purchase_id: str, request_id: str) -> Dict[str, Any]:
        """デジタルギフトを購入"""
        try:
            # 購入ID存在確認
            purchase_id_obj = DigitalGiftPurchaseID.objects.get(
                purchase_id=purchase_id,
                expires_at__gt=timezone.now()
            )
            
            # リクエストID重複チェック
            if DigitalGiftPurchase.objects.filter(request_id=request_id).exists():
                raise DigitalGiftAPIError(f"Request ID {request_id} already exists")
            
            # API リクエスト
            request_data = {
                'purchase_id': purchase_id,
                'request_id': request_id
            }
            
            response = self._make_request('POST', '/gifts/purchase', data=request_data)
            
            # 購入記録を保存
            gift_purchase = DigitalGiftPurchase.objects.create(
                purchase_id_obj=purchase_id_obj,
                request_id=request_id,
                gift_code=response.get('gift_code', ''),
                gift_url=response.get('gift_url', ''),
                pin_code=response.get('pin_code', ''),
                status='purchased',
                expires_at=timezone.now() + timezone.timedelta(days=365),  # 1年有効
                api_response=response
            )
            
            logger.info(f"Successfully purchased gift: {request_id}")
            
            return {
                'gift_id': gift_purchase.id,
                'gift_code': gift_purchase.gift_code,
                'gift_url': gift_purchase.gift_url,
                'pin_code': gift_purchase.pin_code,
                'expires_at': gift_purchase.expires_at.isoformat(),
                'brand_name': purchase_id_obj.brand.brand_name,
                'price': purchase_id_obj.price
            }
            
        except DigitalGiftPurchaseID.DoesNotExist:
            raise DigitalGiftAPIError("Purchase ID not found or expired")
        except Exception as e:
            logger.error(f"Failed to purchase gift: {e}")
            raise
    
    def get_gift_status(self, request_id: str) -> Dict[str, Any]:
        """ギフト状態を確認"""
        try:
            response = self._make_request('GET', f'/gifts/status/{request_id}')
            
            # データベースの状態も更新
            try:
                gift_purchase = DigitalGiftPurchase.objects.get(request_id=request_id)
                gift_purchase.status = response.get('status', gift_purchase.status)
                gift_purchase.save()
            except DigitalGiftPurchase.DoesNotExist:
                logger.warning(f"Gift purchase record not found for request_id: {request_id}")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get gift status: {e}")
            raise
    
    def log_gift_usage(self, gift_id: int, user_id: int, action: str, 
                      details: dict = None) -> None:
        """ギフト使用ログを記録"""
        try:
            DigitalGiftUsageLog.objects.create(
                gift_id=gift_id,
                user_id=user_id,
                action=action,
                details=details or {},
                timestamp=timezone.now()
            )
            
            logger.info(f"Logged gift usage: gift_id={gift_id}, action={action}")
            
        except Exception as e:
            logger.error(f"Failed to log gift usage: {e}")
            # ログ記録失敗は致命的ではないため、例外を再発生させない
    
    def get_purchase_cost(self, brand_code: str, price: int) -> Dict[str, Any]:
        """購入コストを計算"""
        try:
            brand = DigitalGiftBrand.objects.get(brand_code=brand_code, is_active=True)
            return brand.calculate_total_cost(price)
            
        except DigitalGiftBrand.DoesNotExist:
            raise DigitalGiftAPIError(f"Brand {brand_code} not found or inactive")
    
    def cleanup_expired_purchase_ids(self) -> int:
        """期限切れ購入IDをクリーンアップ"""
        try:
            expired_count = DigitalGiftPurchaseID.objects.filter(
                expires_at__lt=timezone.now(),
                is_used=False
            ).update(is_expired=True)
            
            logger.info(f"Cleaned up {expired_count} expired purchase IDs")
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired purchase IDs: {e}")
            return 0


def get_digital_gift_client() -> DigitalGiftAPIClient:
    """デジタルギフトAPIクライアントのインスタンスを取得"""
    try:
        # アクティブなAPIアクセスキーを取得
        access_key = APIAccessKey.objects.filter(
            is_active=True,
            service_name='digital_gift'
        ).first()
        
        if not access_key:
            raise DigitalGiftAPIError("No active API access key found for digital gift service")
        
        return DigitalGiftAPIClient(access_key)
        
    except Exception as e:
        logger.error(f"Failed to create digital gift client: {e}")
        raise