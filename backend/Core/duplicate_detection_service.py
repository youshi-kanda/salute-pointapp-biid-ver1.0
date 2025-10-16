from django.utils import timezone
from django.db.models import Q, Count
from decimal import Decimal
from datetime import timedelta
import logging

from .models import ECPointRequest, User, Store

logger = logging.getLogger(__name__)


class DuplicateDetectionService:
    """重複検知サービス"""
    
    def __init__(self):
        # 検知パラメータ
        self.time_window_hours = 24  # 24時間以内の重複をチェック
        self.amount_tolerance = Decimal('0.01')  # 金額の許容範囲
        self.order_id_similarity_threshold = 0.8  # 注文ID類似度閾値
    
    def check_for_duplicates(self, user: User, store: Store, amount: Decimal, 
                           order_id: str, purchase_date: timezone.datetime):
        """重複申請をチェック"""
        potential_duplicates = []
        
        # 1. 完全な注文ID重複チェック
        order_id_duplicates = self._check_order_id_duplicates(order_id)
        if order_id_duplicates:
            potential_duplicates.extend([
                {
                    'type': 'order_id',
                    'original': duplicate,
                    'details': {
                        'matching_order_id': order_id,
                        'reason': '同一注文IDが既に存在'
                    },
                    'severity': 'critical'
                } for duplicate in order_id_duplicates
            ])
        
        # 2. パターンマッチング（同一ユーザー・店舗・金額・時間）
        pattern_duplicates = self._check_pattern_duplicates(
            user, store, amount, purchase_date
        )
        if pattern_duplicates:
            potential_duplicates.extend([
                {
                    'type': 'pattern_match',
                    'original': duplicate['request'],
                    'details': {
                        'time_difference_minutes': duplicate['time_diff'],
                        'amount_difference': float(duplicate['amount_diff']),
                        'reason': '同一ユーザー・店舗・金額・時間での重複申請'
                    },
                    'severity': 'high' if duplicate['time_diff'] < 60 else 'medium'
                } for duplicate in pattern_duplicates
            ])
        
        # 3. 不審な活動パターンチェック
        suspicious_patterns = self._check_suspicious_patterns(user, store, amount)
        if suspicious_patterns:
            potential_duplicates.extend([
                {
                    'type': 'suspicious',
                    'original': pattern['request'],
                    'details': pattern['details'],
                    'severity': pattern['severity']
                } for pattern in suspicious_patterns
            ])
        
        return potential_duplicates
    
    def _check_order_id_duplicates(self, order_id: str):
        """注文ID重複チェック"""
        try:
            existing_requests = ECPointRequest.objects.filter(
                order_id=order_id
            ).exclude(
                status='rejected'  # 拒否済みは除外
            )
            
            return list(existing_requests)
            
        except Exception as e:
            logger.error(f"Order ID duplicate check failed: {str(e)}")
            return []
    
    def _check_pattern_duplicates(self, user: User, store: Store, amount: Decimal, 
                                purchase_date: timezone.datetime):
        """パターンマッチング重複チェック"""
        try:
            # 時間範囲を設定
            time_start = purchase_date - timedelta(hours=self.time_window_hours)
            time_end = purchase_date + timedelta(hours=self.time_window_hours)
            
            # 同一ユーザー・店舗での近似申請を検索
            similar_requests = ECPointRequest.objects.filter(
                user=user,
                store=store,
                purchase_date__range=(time_start, time_end),
                purchase_amount__range=(
                    amount - self.amount_tolerance,
                    amount + self.amount_tolerance
                )
            ).exclude(
                status='rejected'
            )
            
            duplicates = []
            for request in similar_requests:
                time_diff = abs((request.purchase_date - purchase_date).total_seconds()) / 60
                amount_diff = abs(request.purchase_amount - amount)
                
                duplicates.append({
                    'request': request,
                    'time_diff': int(time_diff),
                    'amount_diff': amount_diff
                })
            
            return duplicates
            
        except Exception as e:
            logger.error(f"Pattern duplicate check failed: {str(e)}")
            return []
    
    def _check_suspicious_patterns(self, user: User, store: Store, amount: Decimal):
        """不審な活動パターンチェック"""
        try:
            suspicious_patterns = []
            now = timezone.now()
            
            # 1. 短時間での大量申請チェック
            recent_requests = ECPointRequest.objects.filter(
                user=user,
                created_at__gte=now - timedelta(hours=1)
            ).count()
            
            if recent_requests >= 5:  # 1時間に5回以上
                latest_request = ECPointRequest.objects.filter(
                    user=user
                ).order_by('-created_at').first()
                
                suspicious_patterns.append({
                    'request': latest_request,
                    'details': {
                        'reason': '短時間での大量申請',
                        'request_count_per_hour': recent_requests,
                        'threshold': 5
                    },
                    'severity': 'high'
                })
            
            # 2. 同一金額での繰り返し申請チェック
            same_amount_requests = ECPointRequest.objects.filter(
                user=user,
                purchase_amount=amount,
                created_at__gte=now - timedelta(days=7)
            ).count()
            
            if same_amount_requests >= 3:  # 1週間で同じ金額を3回以上
                latest_request = ECPointRequest.objects.filter(
                    user=user,
                    purchase_amount=amount
                ).order_by('-created_at').first()
                
                suspicious_patterns.append({
                    'request': latest_request,
                    'details': {
                        'reason': '同一金額での繰り返し申請',
                        'same_amount_count': same_amount_requests,
                        'amount': float(amount),
                        'period_days': 7
                    },
                    'severity': 'medium'
                })
            
            # 3. 異常に高額な申請チェック
            if amount > Decimal('50000'):  # 5万円以上
                suspicious_patterns.append({
                    'request': None,  # 新規申請なので既存requestはなし
                    'details': {
                        'reason': '高額申請',
                        'amount': float(amount),
                        'threshold': 50000
                    },
                    'severity': 'medium'
                })
            
            # 4. 店舗での異常申請パターンチェック
            store_recent_requests = ECPointRequest.objects.filter(
                store=store,
                created_at__gte=now - timedelta(hours=1)
            ).count()
            
            if store_recent_requests >= 20:  # 1時間に20件以上
                latest_store_request = ECPointRequest.objects.filter(
                    store=store
                ).order_by('-created_at').first()
                
                suspicious_patterns.append({
                    'request': latest_store_request,
                    'details': {
                        'reason': '店舗での大量申請',
                        'store_request_count_per_hour': store_recent_requests,
                        'store_name': store.name,
                        'threshold': 20
                    },
                    'severity': 'high'
                })
            
            return suspicious_patterns
            
        except Exception as e:
            logger.error(f"Suspicious pattern check failed: {str(e)}")
            return []
    
    def check_order_id_similarity(self, order_id1: str, order_id2: str):
        """注文ID類似度チェック"""
        try:
            # 簡単なレーベンシュタイン距離による類似度計算
            distance = self._levenshtein_distance(order_id1.lower(), order_id2.lower())
            max_length = max(len(order_id1), len(order_id2))
            
            if max_length == 0:
                return 1.0
            
            similarity = 1.0 - (distance / max_length)
            return similarity
            
        except Exception as e:
            logger.error(f"Order ID similarity check failed: {str(e)}")
            return 0.0
    
    def _levenshtein_distance(self, s1: str, s2: str):
        """レーベンシュタイン距離を計算"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def get_duplicate_statistics(self, days: int = 30):
        """重複検知統計を取得"""
        try:
            from .models import DuplicateDetection
            
            start_date = timezone.now() - timedelta(days=days)
            
            stats = DuplicateDetection.objects.filter(
                created_at__gte=start_date
            ).values('detection_type', 'severity').annotate(
                count=Count('id')
            )
            
            total_detections = DuplicateDetection.objects.filter(
                created_at__gte=start_date
            ).count()
            
            resolved_detections = DuplicateDetection.objects.filter(
                created_at__gte=start_date,
                is_resolved=True
            ).count()
            
            return {
                'total_detections': total_detections,
                'resolved_detections': resolved_detections,
                'resolution_rate': (resolved_detections / total_detections * 100) if total_detections > 0 else 0,
                'breakdown': list(stats),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Failed to get duplicate statistics: {str(e)}")
            return {
                'total_detections': 0,
                'resolved_detections': 0,
                'resolution_rate': 0,
                'breakdown': [],
                'period_days': days
            }
    
    def resolve_duplicate(self, detection_id: int, resolved_by: User, resolution_note: str = ''):
        """重複検知を解決済みにマーク"""
        try:
            from .models import DuplicateDetection
            
            detection = DuplicateDetection.objects.get(id=detection_id)
            detection.is_resolved = True
            detection.resolved_by = resolved_by
            detection.resolved_at = timezone.now()
            
            if resolution_note:
                if not detection.detection_details:
                    detection.detection_details = {}
                detection.detection_details['resolution_note'] = resolution_note
            
            detection.save()
            
            logger.info(f"Duplicate detection resolved: ID {detection_id} by {resolved_by.username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve duplicate detection: {str(e)}")
            return False