from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
import logging

from .models import Store, DepositTransaction, DepositAutoChargeRule, DepositUsageLog, ECPointRequest
from .deposit_serializers import (
    DepositTransactionSerializer, DepositChargeSerializer, DepositConsumeSerializer,
    DepositAutoChargeRuleSerializer, AutoChargeSetupSerializer, DepositUsageLogSerializer,
    DepositBalanceSerializer
)
from .deposit_service import deposit_service

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def charge_deposit(request, store_id):
    """デポジットチャージ"""
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DepositChargeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # デポジットチャージ実行
        transaction = deposit_service.charge_deposit(
            store=store,
            amount=serializer.validated_data['amount'],
            payment_method=serializer.validated_data['payment_method'],
            payment_reference=serializer.validated_data.get('payment_reference', ''),
            description=serializer.validated_data.get('description', '')
        )
        
        response_serializer = DepositTransactionSerializer(transaction)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to charge deposit: {str(e)}")
        return Response(
            {'error': 'チャージに失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def consume_deposit(request, store_id):
    """デポジット消費"""
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DepositConsumeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # デポジット消費実行
        transaction = deposit_service.consume_deposit(
            store=store,
            amount=serializer.validated_data['amount'],
            used_for=serializer.validated_data['used_for'],
            description=serializer.validated_data.get('description', ''),
            user_count=serializer.validated_data.get('user_count', 0)
        )
        
        response_serializer = DepositTransactionSerializer(transaction)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to consume deposit: {str(e)}")
        return Response(
            {'error': 'デポジット消費に失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_deposit_balance(request, store_id):
    """デポジット残高取得"""
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        balance_info = deposit_service.get_deposit_balance(store)
        serializer = DepositBalanceSerializer(balance_info)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Failed to get deposit balance: {str(e)}")
        return Response(
            {'error': '残高取得に失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_deposit_transactions(request, store_id):
    """デポジット取引履歴取得"""
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ページネーション対応
        page = int(request.GET.get('page', 1))
        limit = min(int(request.GET.get('limit', 20)), 100)  # 最大100件
        offset = (page - 1) * limit
        
        transactions = DepositTransaction.objects.filter(
            store=store
        ).order_by('-created_at')[offset:offset + limit]
        
        serializer = DepositTransactionSerializer(transactions, many=True)
        return Response({
            'transactions': serializer.data,
            'page': page,
            'limit': limit,
            'has_more': len(transactions) == limit
        })
        
    except Exception as e:
        logger.error(f"Failed to get deposit transactions: {str(e)}")
        return Response(
            {'error': '取引履歴取得に失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST', 'GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def manage_auto_charge(request, store_id):
    """自動チャージルール管理"""
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.method == 'POST':
            # 自動チャージ設定作成
            serializer = AutoChargeSetupSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            auto_charge_rule = deposit_service.setup_auto_charge(
                store=store,
                **serializer.validated_data
            )
            
            response_serializer = DepositAutoChargeRuleSerializer(auto_charge_rule)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        elif request.method == 'GET':
            # 自動チャージ設定取得
            try:
                auto_charge_rule = store.auto_charge_rule
                serializer = DepositAutoChargeRuleSerializer(auto_charge_rule)
                return Response(serializer.data)
            except DepositAutoChargeRule.DoesNotExist:
                return Response({'error': '自動チャージ設定が見つかりません'}, status=status.HTTP_404_NOT_FOUND)
        
        elif request.method == 'PUT':
            # 自動チャージ設定更新
            try:
                auto_charge_rule = store.auto_charge_rule
            except DepositAutoChargeRule.DoesNotExist:
                return Response({'error': '自動チャージ設定が見つかりません'}, status=status.HTTP_404_NOT_FOUND)
            
            serializer = AutoChargeSetupSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            updated_rule = deposit_service.setup_auto_charge(
                store=store,
                **serializer.validated_data
            )
            
            response_serializer = DepositAutoChargeRuleSerializer(updated_rule)
            return Response(response_serializer.data)
        
        elif request.method == 'DELETE':
            # 自動チャージ設定無効化
            try:
                auto_charge_rule = store.auto_charge_rule
                auto_charge_rule.is_enabled = False
                auto_charge_rule.save()
                return Response({'message': '自動チャージを無効にしました'})
            except DepositAutoChargeRule.DoesNotExist:
                return Response({'error': '自動チャージ設定が見つかりません'}, status=status.HTTP_404_NOT_FOUND)
        
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Failed to manage auto charge: {str(e)}")
        return Response(
            {'error': '自動チャージ設定の処理に失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_usage_logs(request, store_id):
    """デポジット使用履歴取得"""
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ページネーション対応
        page = int(request.GET.get('page', 1))
        limit = min(int(request.GET.get('limit', 20)), 100)
        offset = (page - 1) * limit
        
        # フィルタリング対応
        used_for = request.GET.get('used_for')
        
        queryset = DepositUsageLog.objects.filter(store=store)
        if used_for:
            queryset = queryset.filter(used_for=used_for)
        
        usage_logs = queryset.order_by('-created_at')[offset:offset + limit]
        
        serializer = DepositUsageLogSerializer(usage_logs, many=True)
        return Response({
            'usage_logs': serializer.data,
            'page': page,
            'limit': limit,
            'has_more': len(usage_logs) == limit
        })
        
    except Exception as e:
        logger.error(f"Failed to get usage logs: {str(e)}")
        return Response(
            {'error': '使用履歴取得に失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_ec_deposit_balance(request, store_id):
    """ECポイント用デポジット残高・統計情報取得"""
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum, Count
    
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 基本残高情報
        balance_info = deposit_service.get_deposit_balance(store)
        
        # 今月の期間を計算
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # ECポイント関連の統計情報
        monthly_ec_usage = DepositUsageLog.objects.filter(
            store=store,
            used_for='ec_point_award',
            created_at__gte=month_start
        ).aggregate(
            total_amount=Sum('amount')
        )['total_amount'] or 0
        
        monthly_transactions = ECPointRequest.objects.filter(
            store=store,
            payment_method='deposit_consumption',
            created_at__gte=month_start,
            status='completed'
        ).count()
        
        return Response({
            'balance': balance_info['balance'],
            'monthly_ec_usage': abs(monthly_ec_usage),  # 消費額を正の値で表示
            'monthly_transactions': monthly_transactions,
            'auto_charge_enabled': balance_info.get('auto_charge_enabled', False),
            'auto_charge_threshold': balance_info.get('auto_charge_threshold', 0),
            'updated_at': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get EC deposit balance: {str(e)}")
        return Response(
            {'error': 'ECデポジット残高取得に失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_ec_usage_logs(request, store_id):
    """ECポイント用デポジット使用履歴取得（詳細情報付き）"""
    from datetime import timedelta
    from django.utils import timezone
    
    try:
        store = get_object_or_404(Store, id=store_id)
        
        # 権限チェック（店舗管理者のみ）
        if not hasattr(request.user, 'managed_stores') or not request.user.managed_stores.filter(id=store_id).exists():
            return Response(
                {'error': '権限がありません'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # パラメータ取得
        days = int(request.GET.get('days', 30))
        page = int(request.GET.get('page', 1))
        limit = min(int(request.GET.get('limit', 50)), 100)
        offset = (page - 1) * limit
        
        # 期間フィルタ設定
        if days != -1:  # -1は全期間
            date_from = timezone.now() - timedelta(days=days)
        else:
            date_from = None
        
        # ECポイント関連のデポジット使用履歴を取得
        queryset = DepositUsageLog.objects.filter(
            store=store,
            used_for='ec_point_award'
        ).select_related('store')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        usage_logs = queryset.order_by('-created_at')[offset:offset + limit]
        
        # レスポンス用にデータを整理
        results = []
        for log in usage_logs:
            # 関連するECポイントリクエストを取得
            ec_request = None
            if log.related_object_id:
                try:
                    ec_request = ECPointRequest.objects.get(id=log.related_object_id)
                except ECPointRequest.DoesNotExist:
                    pass
            
            result_data = {
                'id': log.id,
                'created_at': log.created_at,
                'usage_type': log.used_for,
                'amount': log.amount,
                'balance_after': log.balance_after,
                'description': log.description,
                'status': 'completed',  # DepositUsageLogは基本的に完了済み
                'ec_request_id': ec_request.id if ec_request else None,
                'ec_request_order_id': ec_request.order_id if ec_request else None,
                'ec_request_points': ec_request.points_to_award if ec_request else None,
                'ec_request_user': ec_request.user.username if ec_request else None
            }
            results.append(result_data)
        
        return Response({
            'results': results,
            'page': page,
            'limit': limit,
            'has_more': len(usage_logs) == limit,
            'total_period_days': days
        })
        
    except Exception as e:
        logger.error(f"Failed to get EC usage logs: {str(e)}")
        return Response(
            {'error': 'EC使用履歴取得に失敗しました'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )