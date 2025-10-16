"""
Security middleware for fraud prevention
"""
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class SecurityMiddleware(MiddlewareMixin):
    """
    セキュリティ強化のためのミドルウェア
    - レート制限
    - ブルートフォース攻撃対策
    - 異常検知
    - 監査ログ
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit_cache = defaultdict(list)
        self.failed_attempts = defaultdict(int)
        super().__init__(get_response)
    
    def process_request(self, request):
        """リクエスト処理前のセキュリティチェック"""
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        path = request.path
        
        # 1. IPブロックチェック
        if self.is_ip_blocked(client_ip):
            self.log_security_event('BLOCKED_IP_ACCESS', {
                'ip': client_ip,
                'path': path,
                'user_agent': user_agent
            })
            return JsonResponse({
                'error': 'Access denied',
                'message': 'Your IP address has been blocked due to suspicious activity'
            }, status=403)
        
        # 2. レート制限チェック
        if self.is_rate_limited(client_ip, path):
            self.log_security_event('RATE_LIMIT_EXCEEDED', {
                'ip': client_ip,
                'path': path,
                'user_agent': user_agent
            })
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.'
            }, status=429)
        
        # 3. 異常パターン検知
        if self.detect_anomaly(client_ip, path, user_agent):
            self.log_security_event('ANOMALY_DETECTED', {
                'ip': client_ip,
                'path': path,
                'user_agent': user_agent,
                'detection_type': 'suspicious_pattern'
            })
        
        return None
    
    def process_response(self, request, response):
        """レスポンス処理後のセキュリティログ"""
        client_ip = self.get_client_ip(request)
        
        # ログイン失敗時の処理
        if (request.path.startswith('/api/auth/login/') and 
            response.status_code == 401):
            self.handle_login_failure(client_ip, request)
        
        # 成功時の処理
        elif (request.path.startswith('/api/auth/login/') and 
              response.status_code == 200):
            self.handle_login_success(client_ip, request)
        
        return response
    
    def get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_ip_blocked(self, ip):
        """IPブロック状態をチェック"""
        blocked_ips = cache.get('blocked_ips', set())
        return ip in blocked_ips
    
    def block_ip(self, ip, duration=3600):
        """IPアドレスをブロック"""
        blocked_ips = cache.get('blocked_ips', set())
        blocked_ips.add(ip)
        cache.set('blocked_ips', blocked_ips, duration)
        
        self.log_security_event('IP_BLOCKED', {
            'ip': ip,
            'duration': duration,
            'reason': 'Multiple failed login attempts'
        })
    
    def is_rate_limited(self, ip, path):
        """レート制限チェック"""
        now = time.time()
        cache_key = f'rate_limit:{ip}:{path}'
        
        # パスごとの制限設定
        limits = {
            '/api/auth/login/': {'requests': 5, 'window': 300},  # 5分間に5回
            '/api/points/': {'requests': 100, 'window': 3600},   # 1時間に100回
            'default': {'requests': 50, 'window': 300}           # 5分間に50回
        }
        
        # 適用する制限を決定
        limit_config = limits.get(path, limits['default'])
        for pattern, config in limits.items():
            if pattern != 'default' and path.startswith(pattern):
                limit_config = config
                break
        
        # 現在のリクエスト履歴を取得
        requests = cache.get(cache_key, [])
        
        # 時間枠外のリクエストを削除
        requests = [req_time for req_time in requests 
                   if now - req_time < limit_config['window']]
        
        # 制限チェック
        if len(requests) >= limit_config['requests']:
            return True
        
        # 新しいリクエストを記録
        requests.append(now)
        cache.set(cache_key, requests, limit_config['window'])
        
        return False
    
    def detect_anomaly(self, ip, path, user_agent):
        """異常パターンを検知"""
        # 1. 短時間での大量アクセス
        now = time.time()
        cache_key = f'anomaly_check:{ip}'
        recent_requests = cache.get(cache_key, [])
        recent_requests = [req_time for req_time in recent_requests 
                          if now - req_time < 60]  # 1分間
        
        if len(recent_requests) > 20:  # 1分間に20回以上
            return True
        
        recent_requests.append(now)
        cache.set(cache_key, recent_requests, 60)
        
        # 2. 異常なUser-Agent
        suspicious_agents = [
            'curl', 'wget', 'python', 'bot', 'crawler', 'scanner'
        ]
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            return True
        
        # 3. 異常なパスアクセス
        if path in ['/admin/', '/.env', '/robots.txt', '/sitemap.xml']:
            return True
        
        return False
    
    def handle_login_failure(self, ip, request):
        """ログイン失敗時の処理"""
        cache_key = f'login_failures:{ip}'
        failures = cache.get(cache_key, 0) + 1
        cache.set(cache_key, failures, 3600)  # 1時間
        
        self.log_security_event('LOGIN_FAILURE', {
            'ip': ip,
            'path': request.path,
            'failures': failures,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')
        })
        
        # 5回失敗でIPブロック
        if failures >= 5:
            self.block_ip(ip, 7200)  # 2時間ブロック
    
    def handle_login_success(self, ip, request):
        """ログイン成功時の処理"""
        # 失敗カウントをリセット
        cache_key = f'login_failures:{ip}'
        cache.delete(cache_key)
        
        self.log_security_event('LOGIN_SUCCESS', {
            'ip': ip,
            'path': request.path,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')
        })
    
    def log_security_event(self, event_type, data):
        """セキュリティイベントのログ記録"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'data': data
        }
        
        # ログファイルに記録
        logger.warning(f"SECURITY_EVENT: {json.dumps(log_entry)}")
        
        # データベースに記録（必要に応じて）
        # SecurityLog.objects.create(
        #     event_type=event_type,
        #     data=json.dumps(data),
        #     timestamp=timezone.now()
        # )


class FraudDetectionMiddleware(MiddlewareMixin):
    """
    不正検知専用のミドルウェア
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """不正検知処理"""
        if request.path.startswith('/api/'):
            # ポイント関連の不正検知
            if 'points' in request.path:
                self.detect_point_fraud(request)
            
            # ギフト交換の不正検知
            if 'gifts/exchange' in request.path:
                self.detect_gift_fraud(request)
        
        return None
    
    def detect_point_fraud(self, request):
        """ポイント関連の不正検知"""
        if request.method == 'POST':
            # 異常に大きなポイント付与の検知
            if hasattr(request, 'data') and 'points' in request.data:
                points = request.data.get('points', 0)
                if points > 100000:  # 10万ポイント以上
                    self.log_fraud_attempt('EXCESSIVE_POINTS', {
                        'points': points,
                        'ip': self.get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')
                    })
    
    def detect_gift_fraud(self, request):
        """ギフト交換の不正検知"""
        if request.method == 'POST':
            client_ip = self.get_client_ip(request)
            
            # 短時間での大量ギフト交換の検知
            cache_key = f'gift_exchange:{client_ip}'
            recent_exchanges = cache.get(cache_key, [])
            now = time.time()
            recent_exchanges = [ex_time for ex_time in recent_exchanges 
                              if now - ex_time < 3600]  # 1時間
            
            if len(recent_exchanges) > 5:  # 1時間に5回以上
                self.log_fraud_attempt('EXCESSIVE_GIFT_EXCHANGE', {
                    'ip': client_ip,
                    'exchanges_count': len(recent_exchanges),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')
                })
            
            recent_exchanges.append(now)
            cache.set(cache_key, recent_exchanges, 3600)
    
    def get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def log_fraud_attempt(self, fraud_type, data):
        """不正試行のログ記録"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'fraud_type': fraud_type,
            'data': data
        }
        
        logger.error(f"FRAUD_ATTEMPT: {json.dumps(log_entry)}")