from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from django.conf import settings
from django.db import models
from datetime import datetime, timedelta
import jwt
from .models import Store, PointTransaction, Gift, GiftCategory, GiftExchange
from .serializers import (
    UserSerializer, StoreSerializer, PointTransactionSerializer, MemberSyncSerializer,
    GiftSerializer, GiftCategorySerializer, GiftExchangeSerializer, GiftExchangeRequestSerializer
)

User = get_user_model()


class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class StoreListCreateView(generics.ListCreateAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer


class StoreDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer


class PointTransactionListCreateView(generics.ListCreateAPIView):
    queryset = PointTransaction.objects.all()
    serializer_class = PointTransactionSerializer


class PointTransactionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PointTransaction.objects.all()
    serializer_class = PointTransactionSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def member_sync(request):
    """
    External member sync endpoint.
    Receives member data and creates or updates existing members.
    """
    serializer = MemberSyncSerializer(data=request.data)
    
    if serializer.is_valid():
        data = serializer.validated_data
        
        try:
            user, created = User.objects.update_or_create(
                member_id=data['member_id'],
                defaults={
                    'username': data['username'],
                    'email': data['email'],
                    'first_name': data.get('first_name', ''),
                    'last_name': data.get('last_name', ''),
                    'points': data['points'],
                    'status': data['status'],
                    'location': data.get('location', ''),
                    'avatar': data.get('avatar', ''),
                }
            )
            
            if created:
                user.registration_date = timezone.now()
            user.last_login_date = timezone.now()
            user.save()
            
            user_serializer = UserSerializer(user)
            
            return Response({
                'success': True,
                'created': created,
                'message': 'Member created successfully' if created else 'Member updated successfully',
                'user': user_serializer.data
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Database error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nfc_lookup(request, uid):
    """
    NFC lookup endpoint.
    Looks up user by UID (member_id or username).
    """
    try:
        try:
            user = User.objects.get(member_id=uid)
        except User.DoesNotExist:
            user = User.objects.get(username=uid)
        
        user_serializer = UserSerializer(user)
        
        return Response({
            'success': True,
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Lookup error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TokenObtainView(APIView):
    permission_classes = []
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({'error': 'Email and password required'}, status=400)
        
        # メールアドレスまたはユーザー名でログイン可能
        user = None
        try:
            # まずメールアドレスで検索
            if '@' in email:
                user_obj = User.objects.get(email=email)
                user = authenticate(username=user_obj.username, password=password)
            else:
                # ユーザー名で直接認証
                user = authenticate(username=email, password=password)
        except User.DoesNotExist:
            # ユーザー名でも試す
            user = authenticate(username=email, password=password)
        
        if not user:
            return Response({'error': 'Invalid credentials'}, status=401)
        
        access_payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        refresh_payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=7)
        }
        
        access_token = jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        refresh_token = jwt.encode(refresh_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        
        return Response({
            'access': access_token,
            'refresh': refresh_token
        })


class TokenRefreshView(APIView):
    permission_classes = []
    
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token required'}, status=400)
        
        try:
            payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get('user_id')
            
            access_payload = {
                'user_id': user_id,
                'exp': datetime.utcnow() + timedelta(hours=1)
            }
            access_token = jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
            
            return Response({'access': access_token})
        except jwt.ExpiredSignatureError:
            return Response({'error': 'Refresh token expired'}, status=401)
        except jwt.InvalidTokenError:
            return Response({'error': 'Invalid refresh token'}, status=401)


class CurrentUserView(APIView):
    def get(self, request):
        user = request.user
        user_serializer = UserSerializer(user)
        
        # MELTY連携ステータス情報を取得
        melty_status = {
            'is_linked': user.is_melty_linked,
            'linked_at': user.melty_connected_at,
            'melty_email': user.melty_email if user.is_melty_linked else None,
            'membership_type': None,
            'membership_display': None
        }
        
        # MELTY設定情報を取得
        if user.is_melty_linked:
            try:
                config = user.get_melty_configuration()
                if config:
                    melty_status['membership_type'] = config.melty_membership_type
                    melty_status['membership_display'] = config.get_melty_membership_type_display()
                    melty_status['welcome_bonus'] = config.welcome_bonus_points
                    melty_status['points_expiry_months'] = config.points_expiry_months
            except:
                pass
        
        # ランク情報を取得
        rank_info = {
            'current_rank': user.rank,
            'rank_display': user.get_rank_display(),
            'point_balance': user.point_balance,
            'registration_source': user.registration_source,
            'registration_source_display': user.get_registration_source_display()
        }
        
        # レスポンスデータを構築
        response_data = user_serializer.data
        response_data['melty_status'] = melty_status
        response_data['rank_info'] = rank_info
        
        return Response({
            'success': True,
            'user': response_data
        })


class PointGrantView(APIView):
    def post(self, request):
        uid = request.data.get('uid')
        points = request.data.get('points')
        reason = request.data.get('reason', '')
        
        if not uid or not points:
            return Response({'error': 'UID and points required'}, status=400)
        
        try:
            try:
                user = User.objects.get(member_id=uid)
            except User.DoesNotExist:
                user = User.objects.get(username=uid)
            
            user.points += int(points)
            user.save()
            
            from .models import Store
            default_store = Store.objects.first()
            
            transaction = PointTransaction.objects.create(
                user=user,
                store=default_store,
                amount=0,
                points_issued=int(points),
                payment_method='grant',
                status='completed',
                description=reason
            )
            
            return Response({
                'success': True,
                'message': f'{points} points granted to {user.username}',
                'user_points': user.points
            })
            
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class PointHistoryView(APIView):
    def get(self, request):
        transactions = PointTransaction.objects.filter(
            points_issued__gt=0
        ).order_by('-transaction_date')[:50]
        
        serializer = PointTransactionSerializer(transactions, many=True)
        return Response({
            'success': True,
            'transactions': serializer.data
        })


class ChargeView(APIView):
    def post(self, request):
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method')
        
        if not amount or not payment_method:
            return Response({'error': 'Amount and payment method required'}, status=400)
        
        try:
            from .models import Store
            default_store = Store.objects.first()
            
            transaction = PointTransaction.objects.create(
                user=request.user,
                store=default_store,
                amount=float(amount),
                points_issued=0,
                payment_method=payment_method,
                status='completed',
                description='Charge transaction'
            )
            
            return Response({
                'success': True,
                'message': f'Charged {amount} yen',
                'transaction_id': transaction.transaction_id
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class ChargeHistoryView(APIView):
    def get(self, request):
        transactions = PointTransaction.objects.filter(
            amount__gt=0
        ).order_by('-transaction_date')[:50]
        
        serializer = PointTransactionSerializer(transactions, many=True)
        return Response({
            'success': True,
            'transactions': serializer.data
        })


class DashboardStatsView(APIView):
    def get(self, request):
        total_users = User.objects.count()
        total_points = sum(User.objects.values_list('points', flat=True))
        total_transactions = PointTransaction.objects.count()
        today_transactions = PointTransaction.objects.filter(
            transaction_date__date=timezone.now().date()
        ).count()
        
        return Response({
            'success': True,
            'stats': {
                'total_users': total_users,
                'total_points_granted': total_points,
                'total_revenue': sum(PointTransaction.objects.filter(amount__gt=0).values_list('amount', flat=True)),
                'average_rating': 4.8,
                'today_transactions': today_transactions,
                'monthly_growth': 12.5
            }
        })


# === ギフト関連API ===

class GiftCategoryListView(generics.ListAPIView):
    queryset = GiftCategory.objects.filter(is_active=True)
    serializer_class = GiftCategorySerializer
    permission_classes = [IsAuthenticated]


class GiftListView(generics.ListAPIView):
    serializer_class = GiftSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Gift.objects.filter(status='active')
        
        # カテゴリでフィルタ
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # ギフトタイプでフィルタ
        gift_type = self.request.query_params.get('type')
        if gift_type:
            queryset = queryset.filter(gift_type=gift_type)
        
        # 在庫有りのみ
        in_stock = self.request.query_params.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(
                models.Q(unlimited_stock=True) | models.Q(stock_quantity__gt=0)
            )
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # 在庫状況を追加
        for item in serializer.data:
            gift = Gift.objects.get(id=item['id'])
            item['is_available'] = gift.is_available()
        
        return Response({
            'success': True,
            'gifts': serializer.data,
            'total_count': queryset.count()
        })


class GiftDetailView(generics.RetrieveAPIView):
    queryset = Gift.objects.all()
    serializer_class = GiftSerializer
    permission_classes = [IsAuthenticated]
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data['is_available'] = instance.is_available()
        
        return Response({
            'success': True,
            'gift': data
        })


class GiftExchangeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """ギフト交換処理"""
        serializer = GiftExchangeRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        gift_id = serializer.validated_data['gift_id']
        user = request.user
        
        try:
            gift = Gift.objects.get(id=gift_id)
        except Gift.DoesNotExist:
            return Response({
                'success': False,
                'error': 'ギフトが見つかりません'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ギフトの利用可能性をチェック
        if not gift.is_available():
            return Response({
                'success': False,
                'error': 'このギフトは現在交換できません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ユーザーのポイント残高をチェック
        if user.points < gift.points_required:
            return Response({
                'success': False,
                'error': f'ポイントが不足しています（必要: {gift.points_required}pt, 所持: {user.points}pt）'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 在庫をチェック
        if not gift.unlimited_stock and gift.stock_quantity <= 0:
            return Response({
                'success': False,
                'error': '在庫が不足しています'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # トランザクション内で処理
            from django.db import transaction
            with transaction.atomic():
                # ポイントを減算
                user.points -= gift.points_required
                user.save()
                
                # 在庫を減らす
                if not gift.unlimited_stock:
                    gift.stock_quantity -= 1
                    gift.save()
                
                # 交換回数を増やす
                gift.exchange_count += 1
                gift.save()
                
                # 交換記録を作成
                exchange = GiftExchange.objects.create(
                    user=user,
                    gift=gift,
                    points_spent=gift.points_required,
                    exchange_code=GiftExchange().generate_exchange_code(),
                    delivery_method=serializer.validated_data.get('delivery_method', ''),
                    delivery_address=serializer.validated_data.get('delivery_address', ''),
                    recipient_name=serializer.validated_data.get('recipient_name', ''),
                    recipient_email=serializer.validated_data.get('recipient_email', ''),
                    recipient_phone=serializer.validated_data.get('recipient_phone', ''),
                    notes=serializer.validated_data.get('notes', '')
                )
                
                # デジタルギフトの場合、即座に処理
                if gift.gift_type == 'digital':
                    exchange.status = 'completed'
                    exchange.processed_at = timezone.now()
                    exchange.digital_code = self._generate_digital_code(gift)
                    exchange.save()
                
                # ポイント取引記録を作成
                PointTransaction.objects.create(
                    user=user,
                    store=Store.objects.first(),
                    transaction_id=f"GFT-{exchange.exchange_code}",
                    amount=0,
                    points_issued=-gift.points_required,
                    payment_method='gift_exchange',
                    status='completed',
                    description=f'ギフト交換: {gift.name}'
                )
                
                serializer = GiftExchangeSerializer(exchange)
                return Response({
                    'success': True,
                    'message': 'ギフト交換が完了しました',
                    'exchange': serializer.data,
                    'remaining_points': user.points
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': f'交換処理中にエラーが発生しました: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generate_digital_code(self, gift):
        """デジタルギフトコード生成（モック）"""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))


class GiftExchangeHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """ギフト交換履歴取得"""
        exchanges = GiftExchange.objects.filter(user=request.user)
        serializer = GiftExchangeSerializer(exchanges, many=True)
        
        return Response({
            'success': True,
            'exchanges': serializer.data,
            'total_count': exchanges.count()
        })


class GiftExchangeDetailView(generics.RetrieveAPIView):
    queryset = GiftExchange.objects.all()
    serializer_class = GiftExchangeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return GiftExchange.objects.filter(user=self.request.user)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response({
            'success': True,
            'exchange': serializer.data
        })


# Point Purchase and Billing Views
class PointPurchaseView(APIView):
    """ユーザーへのポイント付与（従量課金）"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from .services.point_purchase_service import PointPurchaseService
            
            # リクエストデータ取得
            user_id = request.data.get('user_id')
            points_amount = request.data.get('points_amount')
            description = request.data.get('description', '')
            payment_method_preference = request.data.get('payment_method_preference')
            
            # バリデーション
            if not user_id or not points_amount:
                return Response({
                    'success': False,
                    'error': 'user_id と points_amount は必須です'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                target_user = User.objects.get(id=user_id, role='customer')
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': '指定されたユーザーが見つかりません'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 店舗取得（現在のユーザーが管理する店舗）
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            
            # ポイント購入サービス実行
            purchase_service = PointPurchaseService(store)
            transaction = purchase_service.purchase_points_for_user(
                user=target_user,
                points_amount=int(points_amount),
                description=description,
                payment_method_preference=payment_method_preference
            )
            
            return Response({
                'success': True,
                'message': f'{target_user.username}さんに{points_amount}ポイントを付与しました',
                'transaction': {
                    'transaction_id': transaction.transaction_id,
                    'points_amount': transaction.points_amount,
                    'total_amount': transaction.total_amount,
                    'payment_method': transaction.payment_method,
                    'status': transaction.payment_status
                }
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'ポイント付与に失敗しました: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PointPurchaseTransactionListView(APIView):
    """ポイント購入取引履歴"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from .models import PointPurchaseTransaction
            
            # 店舗取得
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            limit = int(request.GET.get('limit', 10))
            
            transactions = PointPurchaseTransaction.objects.filter(
                store=store
            ).select_related('target_user', 'monthly_billing').order_by('-created_at')[:limit]
            
            transaction_data = []
            for t in transactions:
                transaction_data.append({
                    'id': t.id,
                    'transaction_id': t.transaction_id,
                    'target_user': {
                        'id': t.target_user.id,
                        'username': t.target_user.username,
                        'first_name': t.target_user.first_name,
                        'last_name': t.target_user.last_name,
                        'email': t.target_user.email
                    },
                    'points_amount': t.points_amount,
                    'total_amount': t.total_amount,
                    'payment_method': t.payment_method,
                    'payment_status': t.payment_status,
                    'description': t.description,
                    'created_at': t.created_at.isoformat(),
                    'completed_at': t.completed_at.isoformat() if t.completed_at else None
                })
            
            return Response({
                'success': True,
                'data': transaction_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PointPurchaseSummaryView(APIView):
    """ポイント購入サマリー"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from .services.point_purchase_service import PointPurchaseService
            from datetime import date
            
            # 店舗取得
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            period = request.GET.get('period', 'today')  # today, month, year
            
            purchase_service = PointPurchaseService(store)
            
            if period == 'today':
                summary = purchase_service.get_daily_summary()
            elif period == 'month':
                today = date.today()
                summary = purchase_service.get_monthly_usage(today.year, today.month)
            else:
                summary = purchase_service.get_daily_summary()
            
            return Response({
                'success': True,
                'data': summary
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingHistoryView(APIView):
    """請求履歴"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from .services.billing_service import BillingService
            
            # 店舗取得
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            billing_service = BillingService(store)
            
            billings = billing_service.get_billing_history()
            
            billing_data = []
            for b in billings:
                billing_data.append({
                    'id': b.id,
                    'billing_id': b.billing_id,
                    'billing_year': b.billing_year,
                    'billing_month': b.billing_month,
                    'billing_period_display': b.billing_period_display,
                    'total_points_purchased': b.total_points_purchased,
                    'subtotal': b.subtotal,
                    'tax': b.tax,
                    'total_amount': b.total_amount,
                    'deposit_used': b.deposit_used,
                    'credit_charged': b.credit_charged,
                    'status': b.status,
                    'created_at': b.created_at.isoformat(),
                    'finalized_at': b.finalized_at.isoformat() if b.finalized_at else None,
                    'due_date': b.due_date.isoformat() if b.due_date else None,
                    'paid_at': b.paid_at.isoformat() if b.paid_at else None
                })
            
            return Response({
                'success': True,
                'data': billing_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingSummaryView(APIView):
    """請求サマリー"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from .services.billing_service import BillingService
            
            # 店舗取得
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            billing_service = BillingService(store)
            
            summary = billing_service.get_billing_summary()
            
            return Response({
                'success': True,
                'data': summary
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingAnalyticsView(APIView):
    """請求分析データ"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            from .services.billing_service import BillingService
            
            # 店舗取得
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            billing_service = BillingService(store)
            
            months = int(request.GET.get('months', 12))
            analytics = billing_service.get_analytics_data(months)
            
            return Response({
                'success': True,
                'data': analytics
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FinalizeBillingView(APIView):
    """請求書確定"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from .services.billing_service import BillingService
            
            billing_id = request.data.get('billing_id')
            if not billing_id:
                return Response({
                    'success': False,
                    'error': 'billing_id は必須です'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 店舗取得
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            billing_service = BillingService(store)
            
            billing = billing_service.finalize_billing(billing_id)
            
            return Response({
                'success': True,
                'message': '請求書を確定しました',
                'billing': {
                    'billing_id': billing.billing_id,
                    'status': billing.status,
                    'total_amount': billing.total_amount
                }
            })
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'請求書の確定に失敗しました: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendBillingEmailView(APIView):
    """請求書メール送信"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from .services.billing_service import BillingService
            
            billing_id = request.data.get('billing_id')
            if not billing_id:
                return Response({
                    'success': False,
                    'error': 'billing_id は必須です'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 店舗取得
            if not hasattr(request.user, 'store'):
                return Response({
                    'success': False,
                    'error': '店舗管理者権限が必要です'
                }, status=status.HTTP_403_FORBIDDEN)
            
            store = request.user.store
            billing_service = BillingService(store)
            
            success = billing_service.send_billing_email(billing_id)
            
            if success:
                return Response({
                    'success': True,
                    'message': '請求書メールを送信しました'
                })
            else:
                return Response({
                    'success': False,
                    'error': '請求書メールの送信に失敗しました'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'請求書メールの送信に失敗しました: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Social Skin API Views
class SocialSkinView(APIView):
    """Social skin selection API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """現在のスキン状態と解放済みスキン一覧を返す"""
        user = request.user
        
        return Response({
            'success': True,
            'data': {
                'selected_social_skin': user.selected_social_skin,
                'unlocked_social_skins': user.unlocked_social_skins,
                'available_skins': [
                    {'value': 'classic', 'label': 'Classic', 'description': 'シンプルで上品なクラシックスキン'},
                    {'value': 'modern', 'label': 'Modern', 'description': 'スタイリッシュなモダンスキン'},
                    {'value': 'casual', 'label': 'Casual', 'description': 'カジュアルで親しみやすいスキン'}
                ],
                'has_selected_skin': bool(user.selected_social_skin)
            }
        })
    
    def post(self, request):
        """ユーザーが選択したスキン名を保存する"""
        skin_name = request.data.get('skin_name')
        
        if not skin_name:
            return Response({
                'success': False,
                'error': 'skin_name は必須です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 有効なスキン名かチェック
        valid_skins = [choice[0] for choice in User.SOCIAL_SKIN_CHOICES]
        if skin_name not in valid_skins:
            return Response({
                'success': False,
                'error': f'無効なスキン名です。有効な値: {valid_skins}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # ユーザーが解放済みのスキンかチェック
        if skin_name not in user.unlocked_social_skins:
            return Response({
                'success': False,
                'error': 'このスキンは解放されていません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # スキンを保存
            user.selected_social_skin = skin_name
            user.save()
            
            return Response({
                'success': True,
                'message': f'{skin_name}スキンを選択しました',
                'data': {
                    'selected_social_skin': user.selected_social_skin,
                    'unlocked_social_skins': user.unlocked_social_skins
                }
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'スキンの保存に失敗しました: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
