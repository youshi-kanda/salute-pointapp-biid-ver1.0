"""
本番環境用セキュリティミドルウェア
"""

import logging
import time
import hashlib
from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from .models import SecurityLog, APIRateLimit

logger = logging.getLogger('core.security')


class ProductionSecurityMiddleware(MiddlewareMixin):
    """本番環境用セキュリティ強化ミドルウェア"""
    
    def process_request(self, request):
        # IP制限チェック（本番環境のみ）
        if not settings.DEBUG:
            if self._is_blocked_ip(request):
                return JsonResponse({
                    'error': 'ACCESS_DENIED', 
                    'message': 'アクセスが拒否されました'
                }, status=403)
        
        # APIレート制限
        if request.path.startswith('/api/'):
            rate_limit_response = self._check_rate_limit(request)
            if rate_limit_response:
                return rate_limit_response
        
        # セキュリティヘッダーの追加
        return None
    
    def process_response(self, request, response):
        # 本番環境用セキュリティヘッダー
        if not settings.DEBUG:
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response['Content-Security-Policy'] = "default-src 'self'"
            
        return response
    
    def _is_blocked_ip(self, request):
        """IPブロック判定"""
        ip = self._get_client_ip(request)
        
        # 管理者許可IP（環境変数で設定）
        allowed_ips = getattr(settings, 'ALLOWED_IPS', [])
        if allowed_ips and ip not in allowed_ips:
            return True
            
        # ブロックリストチェック
        blocked_ips = cache.get('blocked_ips', set())
        return ip in blocked_ips
    
    def _check_rate_limit(self, request):
        """APIレート制限チェック"""
        ip = self._get_client_ip(request)
        endpoint = request.path
        
        # レート制限設定（環境変数で調整可能）
        rate_limits = {
            '/api/fincode/payment/initiate/': (10, 300),  # 10回/5分
            '/api/user/login/': (5, 300),                 # 5回/5分
            '/api/': (100, 60),                           # デフォルト: 100回/1分
        }
        
        # 適用するレート制限を決定
        limit_count, window_seconds = rate_limits.get(endpoint, rate_limits['/api/'])
        
        # キーの生成
        window_start = int(time.time()) // window_seconds * window_seconds
        cache_key = f"rate_limit:{ip}:{endpoint}:{window_start}"
        
        # 現在のリクエスト数を取得・更新
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit_count:
            # レート制限超過のログ記録
            self._log_rate_limit_exceeded(request, ip, endpoint, current_count)
            return JsonResponse({
                'error': 'RATE_LIMIT_EXCEEDED',
                'message': 'リクエスト回数の上限を超えました。しばらく時間をおいて再試行してください。'
            }, status=429)
        
        # リクエスト数を増加
        cache.set(cache_key, current_count + 1, window_seconds)
        
        # APIRateLimitモデルに記録（本番環境では監視用）
        if not settings.DEBUG:
            APIRateLimit.objects.update_or_create(
                ip_address=ip,
                endpoint=endpoint,
                window_start=time.time(),
                defaults={'request_count': current_count + 1}
            )
        
        return None
    
    def _get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _log_rate_limit_exceeded(self, request, ip, endpoint, count):
        """レート制限超過のログ記録"""
        try:
            user = request.user if not isinstance(request.user, AnonymousUser) else None
            SecurityLog.objects.create(
                user=user,
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                event_type='RATE_LIMIT_EXCEEDED',
                event_details={
                    'endpoint': endpoint,
                    'request_count': count,
                    'timestamp': time.time()
                },
                risk_score=5  # 中リスク
            )
        except Exception as e:
            logger.error(f"SecurityLog記録エラー: {e}")


class APIAuthenticationMiddleware(MiddlewareMixin):
    """API認証強化ミドルウェア"""
    
    def process_request(self, request):
        # API エンドポイントのみ対象
        if not request.path.startswith('/api/'):
            return None
            
        # 管理画面APIの場合、特別な認証が必要
        if request.path.startswith('/api/admin/'):
            return self._check_admin_api_auth(request)
            
        # 決済APIの場合、より厳しい認証
        if request.path.startswith('/api/fincode/'):
            return self._check_payment_api_auth(request)
            
        return None
    
    def _check_admin_api_auth(self, request):
        """管理API認証チェック"""
        # 管理APIは本番環境では特定のトークンが必要
        if not settings.DEBUG:
            admin_token = request.headers.get('X-Admin-Token')
            expected_token = getattr(settings, 'ADMIN_API_TOKEN', '')
            
            if not admin_token or admin_token != expected_token:
                return JsonResponse({
                    'error': 'ADMIN_AUTH_REQUIRED',
                    'message': '管理API認証が必要です'
                }, status=401)
        return None
    
    def _check_payment_api_auth(self, request):
        """決済API認証チェック"""
        # 決済APIは追加のセキュリティチェック
        if not settings.DEBUG:
            # IPアドレスの検証（決済API用）
            ip = self._get_client_ip(request)
            allowed_payment_ips = getattr(settings, 'ALLOWED_PAYMENT_IPS', [])
            
            if allowed_payment_ips and ip not in allowed_payment_ips:
                # セキュリティログに記録
                self._log_unauthorized_payment_access(request, ip)
                return JsonResponse({
                    'error': 'PAYMENT_ACCESS_DENIED',
                    'message': '決済APIへのアクセスが許可されていません'
                }, status=403)
        return None
    
    def _get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _log_unauthorized_payment_access(self, request, ip):
        """不正な決済APIアクセスのログ記録"""
        try:
            SecurityLog.objects.create(
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                event_type='UNAUTHORIZED_PAYMENT_ACCESS',
                event_details={
                    'path': request.path,
                    'method': request.method,
                    'timestamp': time.time()
                },
                risk_score=8  # 高リスク
            )
        except Exception as e:
            logger.error(f"SecurityLog記録エラー: {e}")


class AuditLogMiddleware(MiddlewareMixin):
    """監査ログミドルウェア"""
    
    def process_response(self, request, response):
        # 本番環境でのみ詳細ログを記録
        if not settings.DEBUG and request.path.startswith('/api/'):
            try:
                self._create_audit_log(request, response)
            except Exception as e:
                logger.error(f"監査ログ記録エラー: {e}")
        
        return response
    
    def _create_audit_log(self, request, response):
        """監査ログの作成"""
        from .models import AuditLog
        
        # 重要なAPIエンドポイントのみログ記録
        important_endpoints = [
            '/api/fincode/',
            '/api/admin/',
            '/api/user/register/',
            '/api/user/login/',
            '/api/points/',
            '/api/payment/'
        ]
        
        if any(request.path.startswith(endpoint) for endpoint in important_endpoints):
            user = request.user if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser) else None
            
            AuditLog.objects.create(
                user=user,
                action_type=request.method,
                object_type='API',
                object_repr=request.path,
                changes={
                    'status_code': response.status_code,
                    'content_length': len(response.content) if hasattr(response, 'content') else 0,
                    'ip_address': self._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
                }
            )
    
    def _get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip