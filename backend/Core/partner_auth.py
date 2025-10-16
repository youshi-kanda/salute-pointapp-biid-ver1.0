import pyotp
import hashlib
import hmac
import time
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .models import APIAccessKey, APIRateLimit


class TOTPAuthenticationError(Exception):
    """TOTP認証エラー"""
    pass


class RateLimitExceededError(Exception):
    """レート制限エラー"""
    pass


class PartnerAPIMiddleware:
    """パートナーAPI認証・レート制限ミドルウェア"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.partner_api_paths = ['/api/partner/']
        self.rate_limit_window = 60  # 1分
        self.rate_limit_requests = 300  # 300リクエスト/分
    
    def __call__(self, request):
        # パートナーAPIパスのチェック
        if any(request.path.startswith(path) for path in self.partner_api_paths):
            try:
                # 認証チェック
                access_key = self._authenticate_request(request)
                
                # レート制限チェック
                self._check_rate_limit(access_key, request)
                
                # リクエストにaccess_keyを追加
                request.partner_access_key = access_key
                
            except TOTPAuthenticationError as e:
                return JsonResponse({
                    'error': 'Authentication failed',
                    'message': str(e)
                }, status=401)
            except RateLimitExceededError as e:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': str(e)
                }, status=429)
            except Exception as e:
                return JsonResponse({
                    'error': 'Internal server error',
                    'message': str(e)
                }, status=503)
        
        response = self.get_response(request)
        return response
    
    def _authenticate_request(self, request):
        """TOTP認証処理"""
        # ヘッダーからトークンとアクセスキーを取得
        totp_token = request.META.get('HTTP_X_REALPAY_GIFT_API_ACCESS_TOKEN')
        access_key_value = request.META.get('HTTP_X_REALPAY_GIFT_API_ACCESS_KEY')
        
        if not totp_token or not access_key_value:
            raise TOTPAuthenticationError('Missing authentication headers')
        
        # アクセスキーを検索
        try:
            access_key = APIAccessKey.objects.get(
                key=access_key_value,
                is_active=True
            )
        except APIAccessKey.DoesNotExist:
            raise TOTPAuthenticationError('Invalid access key')
        
        # TOTP検証
        if not self._verify_totp(totp_token, access_key):
            raise TOTPAuthenticationError('Invalid TOTP token')
        
        # 最終使用時刻を更新
        access_key.last_used = timezone.now()
        access_key.save()
        
        return access_key
    
    def _verify_totp(self, token, access_key):
        """TOTP検証"""
        try:
            # TOTPオブジェクトを作成
            totp = pyotp.TOTP(
                access_key.shared_secret,
                interval=access_key.time_step,
                digits=access_key.totp_digits,
                digest=getattr(hashlib, access_key.hash_algorithm.lower())
            )
            
            # 現在時刻と前後のウィンドウで検証
            current_time = int(time.time())
            for time_offset in [-60, -30, 0, 30, 60]:
                if totp.verify(token, for_time=current_time + time_offset):
                    return True
            
            # デバッグ用: 期待されるトークンを確認
            expected_token = totp.now()
            print(f"DEBUG: Expected TOTP: {expected_token}, Received: {token}")
            
            return False
            
        except Exception as e:
            print(f"DEBUG: TOTP verification error: {e}")
            return False
    
    def _check_rate_limit(self, access_key, request):
        """レート制限チェック"""
        ip_address = self._get_client_ip(request)
        now = timezone.now()
        window_start = now - timezone.timedelta(seconds=self.rate_limit_window)
        
        # 現在のウィンドウでのリクエスト数を取得・更新
        rate_limit, created = APIRateLimit.objects.get_or_create(
            access_key=access_key,
            ip_address=ip_address,
            defaults={
                'request_count': 0,
                'window_start': now
            }
        )
        
        # ウィンドウがリセットされた場合
        if rate_limit.window_start < window_start:
            rate_limit.request_count = 0
            rate_limit.window_start = now
        
        # レート制限チェック
        if rate_limit.request_count >= self.rate_limit_requests:
            raise RateLimitExceededError(
                f'Rate limit exceeded. Max {self.rate_limit_requests} requests per minute'
            )
        
        # リクエスト数をインクリメント
        rate_limit.request_count += 1
        rate_limit.save()
    
    def _get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class PartnerAPIAuthMixin:
    """パートナーAPI認証ミックスイン"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        # パートナーAPIの認証はミドルウェアで実行済み
        # Django REST Frameworkの認証をバイパス
        return super().dispatch(request, *args, **kwargs)
    
    def get_permissions(self):
        """パートナーAPIは独自認証を使用するため、DRF権限をバイパス"""
        from rest_framework.permissions import AllowAny
        return [AllowAny()]
    
    def get_partner_access_key(self):
        """パートナーアクセスキーを取得"""
        return getattr(self.request, 'partner_access_key', None)
    
    def validate_request_id(self, request_id):
        """リクエストIDの重複チェック"""
        from .models import GiftPurchase
        
        if GiftPurchase.objects.filter(request_id=request_id).exists():
            raise ValueError('Request ID already exists')
        
        return request_id


def generate_totp_secret():
    """TOTP用の共通鍵生成"""
    return pyotp.random_base32()


def generate_access_key():
    """アクセスキー生成"""
    import secrets
    import string
    
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(40))