from rest_framework import status, permissions, generics
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
import logging
import time
from decimal import Decimal

from .models import (
    ECPointRequest, StoreWebhookKey, PointAwardLog, DuplicateDetection,
    Store, User, PointTransaction, Notification
)
from .ec_point_serializers import (
    ECPointRequestSerializer, ReceiptUploadSerializer, WebhookRequestSerializer,
    StoreApprovalSerializer, PointAwardLogSerializer, DuplicateDetectionSerializer,
    StoreWebhookKeySerializer, ECRequestListSerializer, ECRequestDetailSerializer
)
from .point_service import point_service
from .deposit_service import deposit_service
from .duplicate_detection_service import DuplicateDetectionService
from .notification_service import NotificationService
from .ec_payment_service import ec_payment_service

logger = logging.getLogger(__name__)


# === レシートアップロード機能 ===

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_receipt(request):
    """レシートアップロードによるポイント申請"""
    try:
        # 顧客のみアクセス可能
        if request.user.role != 'customer':
            return Response({
                'error': '顧客のみが申請可能です'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # シリアライザーでバリデーション
        serializer = ReceiptUploadSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'error': 'バリデーションエラー',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 重複検知チェック
        duplicate_service = DuplicateDetectionService()
        potential_duplicates = duplicate_service.check_for_duplicates(
            user=request.user,
            store=serializer.validated_data['store_name'],  # 既にStoreオブジェクト
            amount=serializer.validated_data['purchase_amount'],
            order_id=serializer.validated_data['order_id'],
            purchase_date=serializer.validated_data['purchase_date']
        )
        
        with transaction.atomic():
            # ECポイント申請を作成
            ec_request = serializer.save()
            
            # 重複が検知された場合は記録
            if potential_duplicates:
                for duplicate in potential_duplicates:
                    DuplicateDetection.objects.create(
                        detection_type=duplicate['type'],
                        original_request=duplicate['original'],
                        duplicate_request=ec_request,
                        detection_details=duplicate['details'],
                        severity=duplicate['severity']
                    )
            
            # 店舗に承認依頼通知を送信
            notification_service = NotificationService()
            notification_service.notify_store_approval_request(ec_request)
        
        logger.info(f"Receipt uploaded: User {request.user.username}, Store {ec_request.store.name}, Amount {ec_request.purchase_amount}")
        
        return Response({
            'success': True,
            'request_id': ec_request.id,
            'message': '申請を受け付けました。店舗の承認をお待ちください。',
            'estimated_points': ec_request.points_to_award,
            'has_duplicates': len(potential_duplicates) > 0
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Receipt upload failed: {str(e)}")
        return Response({
            'error': 'アップロードに失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_requests(request):
    """ユーザーの申請履歴を取得"""
    try:
        # 顧客のみアクセス可能
        if request.user.role != 'customer':
            return Response({
                'error': '権限がありません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # クエリパラメータ
        status_filter = request.GET.get('status')
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 50)
        
        # 申請を取得
        queryset = ECPointRequest.objects.filter(user=request.user).order_by('-created_at')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # ページネーション
        paginator = Paginator(queryset, per_page)
        requests_page = paginator.get_page(page)
        
        serializer = ECRequestListSerializer(requests_page, many=True)
        
        return Response({
            'success': True,
            'requests': serializer.data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': requests_page.has_next(),
                'has_previous': requests_page.has_previous()
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get user requests: {str(e)}")
        return Response({
            'error': '申請履歴の取得に失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_request_detail(request, request_id):
    """申請詳細を取得"""
    try:
        ec_request = get_object_or_404(ECPointRequest, id=request_id)
        
        # 権限チェック
        if request.user.role == 'customer':
            # 顧客は自分の申請のみ
            if ec_request.user != request.user:
                return Response({
                    'error': '権限がありません'
                }, status=status.HTTP_403_FORBIDDEN)
        elif request.user.role == 'store_manager':
            # 店舗管理者は自店舗の申請のみ
            if not request.user.managed_stores.filter(id=ec_request.store.id).exists():
                return Response({
                    'error': '権限がありません'
                }, status=status.HTTP_403_FORBIDDEN)
        elif request.user.role not in ['admin', 'terminal']:
            return Response({
                'error': '権限がありません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ECRequestDetailSerializer(ec_request)
        return Response({
            'success': True,
            'request': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Failed to get request detail: {str(e)}")
        return Response({
            'error': '申請詳細の取得に失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# === Webhook機能 ===

@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Webhook認証は独自実装
def webhook_purchase(request):
    """Webhook経由での購入通知受信"""
    start_time = time.time()
    
    try:
        # GETパラメータからデータを取得
        webhook_data = {
            'user_id': request.GET.get('user_id'),
            'amount': request.GET.get('amount'),
            'order_id': request.GET.get('order_id'),
            'store_key': request.GET.get('store_key'),
            'purchase_date': request.GET.get('purchase_date')
        }
        
        # バリデーション
        serializer = WebhookRequestSerializer(data=webhook_data, context={'request': request})
        if not serializer.is_valid():
            logger.warning(f"Invalid webhook request: {serializer.errors}")
            return Response({
                'error': 'Invalid request',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        user = validated_data['user_id']  # 既にUserオブジェクト
        webhook_key = validated_data['store_key']  # 既にStoreWebhookKeyオブジェクト
        store = webhook_key.store
        
        # 購入日時のデフォルト設定
        purchase_date = validated_data.get('purchase_date', timezone.now())
        
        # レート制限チェック
        if not check_rate_limit(webhook_key, request):
            return Response({
                'error': 'Rate limit exceeded'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # 重複検知
        duplicate_service = DuplicateDetectionService()
        potential_duplicates = duplicate_service.check_for_duplicates(
            user=user,
            store=store,
            amount=validated_data['amount'],
            order_id=validated_data['order_id'],
            purchase_date=purchase_date
        )
        
        with transaction.atomic():
            # ECポイント申請を作成
            request_hash = ECPointRequest().generate_request_hash() if hasattr(ECPointRequest(), 'generate_request_hash') else ''
            
            ec_request = ECPointRequest.objects.create(
                request_type='webhook',
                user=user,
                store=store,
                purchase_amount=validated_data['amount'],
                order_id=validated_data['order_id'],
                purchase_date=purchase_date,
                request_hash=request_hash,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                points_to_award=int(validated_data['amount'] // 100)
            )
            
            # 重複検知結果を記録
            if potential_duplicates:
                for duplicate in potential_duplicates:
                    DuplicateDetection.objects.create(
                        detection_type=duplicate['type'],
                        original_request=duplicate['original'],
                        duplicate_request=ec_request,
                        detection_details=duplicate['details'],
                        severity=duplicate['severity']
                    )
            
            # Webhookキーの使用記録を更新
            webhook_key.update_last_used()
            
            # 店舗に承認依頼通知
            notification_service = NotificationService()
            notification_service.notify_store_approval_request(ec_request)
        
        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Webhook processed: Store {store.name}, User {user.username}, Amount {validated_data['amount']}, Time: {processing_time}ms")
        
        return Response({
            'success': True,
            'request_id': ec_request.id,
            'message': 'Purchase notification received',
            'processing_time_ms': processing_time
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# === 店舗承認機能 ===

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_store_pending_requests(request):
    """店舗の承認待ち申請を取得"""
    try:
        # 店舗管理者のみアクセス可能
        if request.user.role != 'store_manager':
            return Response({
                'error': '店舗管理者のみアクセス可能です'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 管理している店舗を取得
        managed_stores = request.user.managed_stores.all()
        if not managed_stores.exists():
            return Response({
                'error': '管理している店舗がありません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # クエリパラメータ
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 50)
        
        # 承認待ちの申請を取得
        queryset = ECPointRequest.objects.filter(
            store__in=managed_stores,
            status='pending'
        ).order_by('-created_at')
        
        # ページネーション
        paginator = Paginator(queryset, per_page)
        requests_page = paginator.get_page(page)
        
        serializer = ECRequestListSerializer(requests_page, many=True)
        
        return Response({
            'success': True,
            'requests': serializer.data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': requests_page.has_next(),
                'has_previous': requests_page.has_previous()
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get pending requests: {str(e)}")
        return Response({
            'error': '承認待ち申請の取得に失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def process_store_approval(request, request_id):
    """店舗による申請の承認・拒否処理"""
    start_time = time.time()
    
    try:
        # 店舗管理者のみアクセス可能
        if request.user.role != 'store_manager':
            return Response({
                'error': '店舗管理者のみアクセス可能です'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # EC申請を取得
        ec_request = get_object_or_404(ECPointRequest, id=request_id)
        
        # 管理権限チェック
        if not request.user.managed_stores.filter(id=ec_request.store.id).exists():
            return Response({
                'error': 'この申請を処理する権限がありません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 処理可能状態チェック
        if not ec_request.can_be_approved():
            return Response({
                'error': 'この申請は既に処理済みです'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # バリデーション
        serializer = StoreApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'バリデーションエラー',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        
        with transaction.atomic():
            if action == 'approve':
                # 承認処理
                result = process_approval(ec_request, request.user, start_time)
                return Response(result['response'], status=result['status'])
            
            elif action == 'reject':
                # 拒否処理
                rejection_reason = serializer.validated_data['rejection_reason']
                ec_request.reject(request.user, rejection_reason)
                
                # ユーザーに拒否通知
                notification_service = NotificationService()
                notification_service.notify_user_rejection(ec_request)
                
                logger.info(f"Request rejected: ID {ec_request.id}, Reason: {rejection_reason}")
                
                return Response({
                    'success': True,
                    'message': '申請を拒否しました',
                    'request_id': ec_request.id
                })
        
    except Exception as e:
        logger.error(f"Approval processing failed: {str(e)}")
        return Response({
            'error': '承認処理に失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def process_approval(ec_request, approved_by, start_time):
    """承認処理の実行"""
    try:
        # 1. 決済処理（クレジット → デポジット）
        payment_result = ec_payment_service.process_point_purchase(
            store=ec_request.store,
            points_amount=ec_request.points_to_award,
            description=f'ECポイント付与: {ec_request.user.username} - {ec_request.order_id}'
        )
        
        if not payment_result['success']:
            # 決済失敗
            return {
                'response': {
                    'success': False,
                    'error': 'ポイント付与に失敗しました',
                    'message': payment_result['message']
                },
                'status': status.HTTP_400_BAD_REQUEST
            }
        
        # 2. 申請を承認状態に更新
        ec_request.approve(
            approved_by, 
            payment_result['payment_method'], 
            payment_result.get('payment_reference', '')
        )
        
        # デポジット取引IDがある場合は関連付け
        if payment_result.get('deposit_transaction_id'):
            ec_request.deposit_transaction_id = payment_result['deposit_transaction_id']
            ec_request.save()
        
        # 3. ユーザーにポイント付与
        point_transaction = point_service.award_points(
            user=ec_request.user,
            points=ec_request.points_to_award,
            description=f'EC購入ポイント付与: {ec_request.store.name}',
            store=ec_request.store,
            reference_id=ec_request.order_id
        )
        
        # 4. ログ記録
        processing_time = int((time.time() - start_time) * 1000)
        PointAwardLog.objects.create(
            ec_request=ec_request,
            point_transaction=point_transaction,
            awarded_points=ec_request.points_to_award,
            award_rate=Decimal('1.0000'),  # 1%固定
            processing_duration_ms=processing_time
        )
        
        # 5. 完了マーク
        ec_request.mark_completed(ec_request.points_to_award)
        
        # 6. ユーザーに付与完了通知
        notification_service = NotificationService()
        notification_service.notify_user_points_awarded(ec_request, payment_result['message'])
        
        logger.info(f"Points awarded: User {ec_request.user.username}, Points {ec_request.points_to_award}, Method: {payment_result['payment_method']}")
        
        return {
            'response': {
                'success': True,
                'message': 'ポイントを付与しました',
                'request_id': ec_request.id,
                'points_awarded': ec_request.points_to_award,
                'payment_method': payment_result['payment_method'],
                'payment_message': payment_result['message'],
                'processing_time_ms': processing_time
            },
            'status': status.HTTP_200_OK
        }
        
    except Exception as e:
        logger.error(f"Point award failed: {str(e)}")
        return {
            'response': {
                'success': False,
                'error': 'ポイント付与処理に失敗しました'
            },
            'status': status.HTTP_500_INTERNAL_SERVER_ERROR
        }


# 不要になった関数を削除（ec_payment_serviceに統合済み）


# === 運営分析ダッシュボード用API ===

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_analytics_daily_trend(request):
    """日別推移データを取得"""
    try:
        # 管理者のみアクセス可能
        if request.user.role != 'admin':
            return Response({
                'error': '管理者のみアクセス可能です'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # パラメータ取得
        days = min(int(request.GET.get('days', 30)), 90)
        
        from datetime import timedelta, date
        from django.db.models import Count, Sum
        
        # 期間設定
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # 日別データ生成
        daily_data = []
        current_date = start_date
        
        while current_date <= end_date:
            day_start = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            day_stats = ECPointRequest.objects.filter(
                created_at__gte=day_start,
                created_at__lt=day_end
            ).aggregate(
                total_requests=Count('id'),
                total_amount=Sum('purchase_amount'),
                pending_count=Count('id', filter=Q(status='pending')),
                approved_count=Count('id', filter=Q(status='approved')),
                completed_count=Count('id', filter=Q(status='completed')),
                rejected_count=Count('id', filter=Q(status='rejected'))
            )
            
            daily_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'total_requests': day_stats['total_requests'] or 0,
                'total_amount': float(day_stats['total_amount'] or 0),
                'pending': day_stats['pending_count'] or 0,
                'approved': day_stats['approved_count'] or 0,
                'completed': day_stats['completed_count'] or 0,
                'rejected': day_stats['rejected_count'] or 0
            })
            
            current_date += timedelta(days=1)
        
        return Response({
            'success': True,
            'period': f'{days}日間',
            'data': daily_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get daily trend: {str(e)}")
        return Response({
            'error': '日別推移データの取得に失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_analytics_store_performance(request):
    """店舗別パフォーマンス分析"""
    try:
        # 管理者のみアクセス可能
        if request.user.role != 'admin':
            return Response({
                'error': '管理者のみアクセス可能です'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # パラメータ取得
        days = min(int(request.GET.get('days', 30)), 90)
        limit = min(int(request.GET.get('limit', 20)), 50)
        
        from datetime import timedelta
        from django.db.models import Count, Sum, Avg
        
        # 期間設定
        date_from = timezone.now() - timedelta(days=days)
        
        # 店舗別統計
        store_stats = ECPointRequest.objects.filter(
            created_at__gte=date_from
        ).values(
            'store__id', 'store__name'
        ).annotate(
            total_requests=Count('id'),
            total_amount=Sum('purchase_amount'),
            avg_amount=Avg('purchase_amount'),
            completed_requests=Count('id', filter=Q(status='completed')),
            pending_requests=Count('id', filter=Q(status='pending')),
            rejected_requests=Count('id', filter=Q(status='rejected')),
            success_rate=Count('id', filter=Q(status__in=['completed', 'approved'])) * 100.0 / Count('id')
        ).order_by('-total_requests')[:limit]
        
        # データ整形
        performance_data = []
        for store in store_stats:
            performance_data.append({
                'store_id': store['store__id'],
                'store_name': store['store__name'],
                'total_requests': store['total_requests'],
                'total_amount': float(store['total_amount'] or 0),
                'avg_amount': float(store['avg_amount'] or 0),
                'completed': store['completed_requests'],
                'pending': store['pending_requests'],
                'rejected': store['rejected_requests'],
                'success_rate': round(store['success_rate'] or 0, 1)
            })
        
        return Response({
            'success': True,
            'period': f'{days}日間',
            'data': performance_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get store performance: {str(e)}")
        return Response({
            'error': '店舗パフォーマンスデータの取得に失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_analytics_payment_analysis(request):
    """決済方法別分析"""
    try:
        # 管理者のみアクセス可能
        if request.user.role != 'admin':
            return Response({
                'error': '管理者のみアクセス可能です'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # パラメータ取得
        days = min(int(request.GET.get('days', 30)), 90)
        
        from datetime import timedelta
        from django.db.models import Count, Sum
        
        # 期間設定
        date_from = timezone.now() - timedelta(days=days)
        
        # 申請タイプ別統計
        type_stats = ECPointRequest.objects.filter(
            created_at__gte=date_from
        ).values('request_type').annotate(
            count=Count('id'),
            total_amount=Sum('purchase_amount')
        )
        
        # 決済方法別統計（完了済み申請のみ）
        payment_stats = ECPointRequest.objects.filter(
            created_at__gte=date_from,
            status='completed',
            payment_method__isnull=False
        ).values('payment_method').annotate(
            count=Count('id'),
            total_amount=Sum('purchase_amount')
        )
        
        # データ整形
        request_types = []
        total_requests = sum(item['count'] for item in type_stats)
        
        for item in type_stats:
            percentage = round((item['count'] / total_requests * 100) if total_requests > 0 else 0, 1)
            request_types.append({
                'type': item['request_type'],
                'count': item['count'],
                'amount': float(item['total_amount'] or 0),
                'percentage': percentage
            })
        
        payment_methods = []
        total_payments = sum(item['count'] for item in payment_stats)
        
        for item in payment_stats:
            percentage = round((item['count'] / total_payments * 100) if total_payments > 0 else 0, 1)
            payment_methods.append({
                'method': item['payment_method'],
                'count': item['count'],
                'amount': float(item['total_amount'] or 0),
                'percentage': percentage
            })
        
        return Response({
            'success': True,
            'period': f'{days}日間',
            'request_types': request_types,
            'payment_methods': payment_methods
        })
        
    except Exception as e:
        logger.error(f"Failed to get payment analysis: {str(e)}")
        return Response({
            'error': '決済分析データの取得に失敗しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# === ユーティリティ関数 ===

def get_client_ip(request):
    """クライアントIPアドレスを取得"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def check_rate_limit(webhook_key, request):
    """レート制限チェック"""
    # 簡単な実装（Redis等を使った本格的な実装が推奨）
    cache_key = f"webhook_rate_limit_{webhook_key.id}"
    
    # Django cacheを使用（要設定）
    try:
        from django.core.cache import cache
        
        current_count = cache.get(cache_key, 0)
        if current_count >= webhook_key.rate_limit_per_minute:
            return False
        
        cache.set(cache_key, current_count + 1, timeout=60)
        return True
        
    except Exception:
        # cacheが設定されていない場合は通す
        return True


class ECRequestManagementView(APIView):
    """運営用EC申請管理ビュー"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """全EC申請の取得（運営管理者用）"""
        # 管理者のみアクセス可能
        if request.user.role != 'admin':
            return Response({
                'error': '管理者のみアクセス可能です'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # クエリパラメータ
            status_filter = request.GET.get('status')
            store_filter = request.GET.get('store_id')
            request_type_filter = request.GET.get('request_type')
            days_filter = int(request.GET.get('days', 30))
            page = int(request.GET.get('page', 1))
            limit = min(int(request.GET.get('limit', 50)), 100)
            
            # 期間フィルタ
            queryset = ECPointRequest.objects.select_related('user', 'store', 'store_approved_by')
            
            if days_filter > 0:
                from datetime import timedelta
                date_from = timezone.now() - timedelta(days=days_filter)
                queryset = queryset.filter(created_at__gte=date_from)
            
            # フィルタリング
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            if store_filter:
                queryset = queryset.filter(store_id=store_filter)
            if request_type_filter:
                queryset = queryset.filter(request_type=request_type_filter)
            
            # 全体統計（フィルタ適用前）
            all_stats = self.get_comprehensive_stats(days_filter)
            
            # フィルタ適用後の結果
            queryset = queryset.order_by('-created_at')
            
            # ページネーション
            offset = (page - 1) * limit
            total_count = queryset.count()
            requests = queryset[offset:offset + limit]
            
            serializer = ECRequestListSerializer(requests, many=True)
            
            return Response({
                'success': True,
                'results': serializer.data,
                'summary': all_stats,
                'pagination': {
                    'current_page': page,
                    'total_pages': (total_count + limit - 1) // limit,
                    'total_count': total_count,
                    'has_next': offset + limit < total_count,
                    'has_previous': page > 1
                },
                'stores': self.get_store_list(),
                'last_updated': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to get admin requests: {str(e)}")
            return Response({
                'error': '申請一覧の取得に失敗しました'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_comprehensive_stats(self, days_filter):
        """包括的な統計情報を取得"""
        from datetime import timedelta
        
        # 期間設定
        if days_filter > 0:
            date_from = timezone.now() - timedelta(days=days_filter)
            queryset = ECPointRequest.objects.filter(created_at__gte=date_from)
        else:
            queryset = ECPointRequest.objects.all()
        
        # 今日の範囲
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_queryset = queryset.filter(created_at__gte=today_start)
        
        # ステータス別集計
        status_counts = queryset.values('status').annotate(count=Count('status'))
        status_summary = {}
        for item in status_counts:
            status_summary[item['status']] = item['count']
        
        # 今日の合計金額
        today_total = today_queryset.aggregate(
            total=Sum('purchase_amount')
        )['total'] or Decimal('0')
        
        # 全体統計
        total_stats = queryset.aggregate(
            total_amount=Sum('purchase_amount'),
            total_points=Sum('points_awarded')
        )
        
        return {
            'total': queryset.count(),
            'pending': status_summary.get('pending', 0),
            'approved': status_summary.get('approved', 0),
            'completed': status_summary.get('completed', 0),
            'rejected': status_summary.get('rejected', 0),
            'failed': status_summary.get('failed', 0),
            'today_total': float(today_total),
            'period_total_amount': float(total_stats['total_amount'] or 0),
            'period_total_points': total_stats['total_points'] or 0,
        }
    
    def get_store_list(self):
        """アクティブな店舗一覧を取得"""
        return list(Store.objects.filter(
            status='active'
        ).values('id', 'name').order_by('name'))
    
    def get_stats(self, queryset):
        """統計情報を取得（旧メソッド - 後方互換性のため残す）"""
        total_count = queryset.count()
        status_counts = queryset.values('status').annotate(count=Count('status'))
        type_counts = queryset.values('request_type').annotate(count=Count('request_type'))
        
        total_amount = queryset.aggregate(
            total=Sum('purchase_amount')
        )['total'] or Decimal('0')
        
        total_points = queryset.aggregate(
            total=Sum('points_awarded')
        )['total'] or 0
        
        return {
            'total_requests': total_count,
            'status_breakdown': {item['status']: item['count'] for item in status_counts},
            'type_breakdown': {item['request_type']: item['count'] for item in type_counts},
            'total_purchase_amount': float(total_amount),
            'total_points_awarded': total_points
        }