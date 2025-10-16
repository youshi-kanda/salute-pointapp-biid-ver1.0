from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator

from .social_models import (
    DetailedReview, ReviewHelpful, Friendship, UserBlock
)
from .social_serializers import DetailedReviewSerializer
from .models import User, Store, Notification


class DetailedReviewViewSet(viewsets.ModelViewSet):
    """詳細レビューシステムAPI"""
    
    serializer_class = DetailedReviewSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """プライバシー設定を考慮したレビュー取得"""
        user = self.request.user
        
        # フレンドリストを取得
        friend_ids = set()
        friendships = Friendship.objects.filter(
            Q(from_user=user, status='accepted') | 
            Q(to_user=user, status='accepted')
        ).values_list('from_user_id', 'to_user_id')
        
        for from_id, to_id in friendships:
            friend_ids.add(from_id if from_id != user.id else to_id)
        
        # ブロックユーザーを除外
        blocked_ids = set()
        blocks = UserBlock.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list('blocker_id', 'blocked_id')
        
        for blocker_id, blocked_id in blocks:
            blocked_ids.add(blocker_id)
            blocked_ids.add(blocked_id)
        
        # 表示可能なレビューを取得
        queryset = DetailedReview.objects.filter(
            is_deleted=False
        ).exclude(
            user_id__in=blocked_ids
        ).select_related('user', 'store')
        
        # プライバシー設定を考慮してフィルタリング
        visible_reviews = []
        for review in queryset:
            if self.can_view_review(user, review, friend_ids):
                visible_reviews.append(review.id)
        
        return DetailedReview.objects.filter(id__in=visible_reviews).order_by('-created_at')
    
    def can_view_review(self, user, review, friend_ids=None):
        """レビューの表示権限をチェック"""
        if review.user == user:
            return True
        
        if review.visibility == 'public':
            return True
        elif review.visibility == 'friends':
            if friend_ids is None:
                return self.are_friends(user, review.user)
            return review.user_id in friend_ids
        else:  # private
            return False
    
    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """自分のレビュー一覧"""
        reviews = DetailedReview.objects.filter(
            user=request.user,
            is_deleted=False
        ).select_related('store').order_by('-created_at')
        
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        paginator = Paginator(reviews, page_size)
        
        try:
            reviews_page = paginator.page(page)
        except:
            reviews_page = paginator.page(1)
        
        serializer = self.get_serializer(reviews_page.object_list, many=True)
        
        return Response({
            'success': True,
            'page': page,
            'total_pages': paginator.num_pages,
            'total_reviews': paginator.count,
            'reviews': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def store_reviews(self, request):
        """特定店舗のレビュー一覧"""
        store_id = request.GET.get('store_id')
        if not store_id:
            return Response({
                'success': False,
                'error': 'store_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Store not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # フレンド関係を取得
        friend_ids = set()
        friendships = Friendship.objects.filter(
            Q(from_user=request.user, status='accepted') | 
            Q(to_user=request.user, status='accepted')
        ).values_list('from_user_id', 'to_user_id')
        
        for from_id, to_id in friendships:
            friend_ids.add(from_id if from_id != request.user.id else to_id)
        
        # 表示可能なレビューを取得
        reviews = DetailedReview.objects.filter(
            store=store,
            is_deleted=False
        ).select_related('user').order_by('-created_at')
        
        visible_reviews = []
        for review in reviews:
            if self.can_view_review(request.user, review, friend_ids):
                visible_reviews.append(review)
        
        # 評価統計を計算
        if visible_reviews:
            total_reviews = len(visible_reviews)
            avg_overall = sum(r.overall_rating for r in visible_reviews) / total_reviews
            avg_service = sum(r.service_rating for r in visible_reviews) / total_reviews
            avg_atmosphere = sum(r.atmosphere_rating for r in visible_reviews) / total_reviews
            avg_value = sum(r.value_rating for r in visible_reviews) / total_reviews
            
            rating_distribution = {str(i): 0 for i in range(1, 6)}
            for review in visible_reviews:
                rating_distribution[str(review.overall_rating)] += 1
        else:
            total_reviews = 0
            avg_overall = avg_service = avg_atmosphere = avg_value = 0
            rating_distribution = {str(i): 0 for i in range(1, 6)}
        
        # ページネーション
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        paginator = Paginator(visible_reviews, page_size)
        
        try:
            reviews_page = paginator.page(page)
        except:
            reviews_page = paginator.page(1)
        
        serializer = self.get_serializer(reviews_page.object_list, many=True)
        
        return Response({
            'success': True,
            'store': {
                'id': store.id,
                'name': store.name,
                'description': store.description,
                'location': store.location,
            },
            'statistics': {
                'total_reviews': total_reviews,
                'average_ratings': {
                    'overall': round(avg_overall, 1),
                    'service': round(avg_service, 1),
                    'atmosphere': round(avg_atmosphere, 1),
                    'value': round(avg_value, 1),
                },
                'rating_distribution': rating_distribution,
            },
            'page': page,
            'total_pages': paginator.num_pages,
            'reviews': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def user_reviews(self, request):
        """特定ユーザーのレビュー一覧"""
        user_id = request.GET.get('user_id')
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # フレンド関係をチェック
        friend_ids = set()
        if target_user != request.user:
            friendships = Friendship.objects.filter(
                Q(from_user=request.user, status='accepted') | 
                Q(to_user=request.user, status='accepted')
            ).values_list('from_user_id', 'to_user_id')
            
            for from_id, to_id in friendships:
                friend_ids.add(from_id if from_id != request.user.id else to_id)
        
        # 表示可能なレビューを取得
        reviews = DetailedReview.objects.filter(
            user=target_user,
            is_deleted=False
        ).select_related('store').order_by('-created_at')
        
        visible_reviews = []
        for review in reviews:
            if self.can_view_review(request.user, review, friend_ids):
                visible_reviews.append(review)
        
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        paginator = Paginator(visible_reviews, page_size)
        
        try:
            reviews_page = paginator.page(page)
        except:
            reviews_page = paginator.page(1)
        
        serializer = self.get_serializer(reviews_page.object_list, many=True)
        
        return Response({
            'success': True,
            'user': {
                'id': target_user.id,
                'username': target_user.username,
                'avatar': target_user.avatar
            },
            'total_reviews': len(visible_reviews),
            'reviews': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """注目レビュー一覧"""
        reviews = self.get_queryset().filter(is_featured=True)[:10]
        serializer = self.get_serializer(reviews, many=True)
        
        return Response({
            'success': True,
            'count': len(reviews),
            'reviews': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """レビュー作成"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # 同じ店舗・同じ日の重複レビューをチェック
            store_id = serializer.validated_data['store'].id
            visit_date = serializer.validated_data['visit_date']
            
            existing_review = DetailedReview.objects.filter(
                user=request.user,
                store_id=store_id,
                visit_date=visit_date,
                is_deleted=False
            ).first()
            
            if existing_review:
                return Response({
                    'success': False,
                    'error': '同じ店舗の同じ日のレビューは既に投稿されています'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            review = serializer.save()
            
            # ユーザーの最終活動日時を更新
            request.user.last_active_at = timezone.now()
            request.user.save()
            
            # 店舗の評価情報を更新
            self.update_store_ratings(review.store)
            
            return Response({
                'success': True,
                'message': 'レビューを投稿しました',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """レビュー編集"""
        instance = self.get_object()
        
        # レビュー投稿者のみ編集可能
        if instance.user != request.user:
            return Response({
                'success': False,
                'error': 'このレビューを編集する権限がありません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        if serializer.is_valid():
            review = serializer.save()
            
            # 店舗の評価情報を更新
            self.update_store_ratings(review.store)
            
            return Response({
                'success': True,
                'message': 'レビューを更新しました',
                'data': serializer.data
            })
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        """レビュー削除（論理削除）"""
        instance = self.get_object()
        
        # レビュー投稿者のみ削除可能
        if instance.user != request.user:
            return Response({
                'success': False,
                'error': 'このレビューを削除する権限がありません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save()
        
        # ユーザーのレビュー数をデクリメント
        request.user.reviews_count = max(0, request.user.reviews_count - 1)
        request.user.save()
        
        # 店舗の評価情報を更新
        self.update_store_ratings(instance.store)
        
        return Response({
            'success': True,
            'message': 'レビューを削除しました'
        })
    
    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """レビューに「役に立った」をマーク"""
        review = self.get_object()
        
        # 自分のレビューにはマークできない
        if review.user == request.user:
            return Response({
                'success': False,
                'error': '自分のレビューには「役に立った」をマークできません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 既にマーク済みかチェック
        existing_helpful = ReviewHelpful.objects.filter(
            user=request.user,
            review=review
        ).first()
        
        if existing_helpful:
            # 既にマーク済みの場合は削除（取り消し）
            existing_helpful.delete()
            review.helpful_count = max(0, review.helpful_count - 1)
            review.save()
            
            return Response({
                'success': True,
                'message': '「役に立った」を取り消しました',
                'action': 'removed',
                'helpful_count': review.helpful_count
            })
        else:
            # 新しくマーク
            ReviewHelpful.objects.create(
                user=request.user,
                review=review
            )
            review.helpful_count += 1
            review.save()
            
            # レビュー投稿者に通知
            if review.user != request.user:
                Notification.objects.create(
                    user=review.user,
                    notification_type='review_helpful',
                    title='レビューが「役に立った」とマークされました',
                    message=f'{request.user.username}さんがあなたのレビューを「役に立った」とマークしました',
                    metadata={
                        'review_id': review.id,
                        'store_id': review.store_id,
                        'from_user_id': request.user.id
                    }
                )
            
            return Response({
                'success': True,
                'message': '「役に立った」をマークしました',
                'action': 'added',
                'helpful_count': review.helpful_count
            })
    
    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """レビューを報告"""
        review = self.get_object()
        reason = request.data.get('reason', '')
        details = request.data.get('details', '')
        
        if review.user == request.user:
            return Response({
                'success': False,
                'error': '自分のレビューは報告できません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 報告フラグを設定
        review.is_reported = True
        review.save()
        
        # 管理者に通知
        try:
            admin_user = User.objects.filter(role='admin').first()
            if admin_user:
                Notification.objects.create(
                    user=admin_user,
                    notification_type='admin_alert',
                    title='レビューが報告されました',
                    message=f'レビューID:{review.id}が報告されました。理由:{reason}',
                    metadata={
                        'review_id': review.id,
                        'store_id': review.store_id,
                        'reported_by': request.user.id,
                        'reason': reason,
                        'details': details
                    }
                )
        except:
            pass
        
        return Response({
            'success': True,
            'message': 'レビューを報告しました。運営チームが確認いたします。'
        })
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """レビュー検索"""
        keyword = request.GET.get('q', '').strip()
        store_name = request.GET.get('store', '').strip()
        min_rating = request.GET.get('min_rating')
        usage_scene = request.GET.get('usage_scene')
        
        if not keyword and not store_name and not min_rating and not usage_scene:
            return Response({
                'success': False,
                'error': '検索条件を指定してください'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset()
        
        # キーワード検索
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword) |
                Q(content__icontains=keyword)
            )
        
        # 店舗名検索
        if store_name:
            queryset = queryset.filter(store__name__icontains=store_name)
        
        # 最低評価フィルタ
        if min_rating:
            try:
                min_rating = float(min_rating)
                queryset = queryset.filter(overall_rating__gte=min_rating)
            except ValueError:
                pass
        
        # 利用シーンフィルタ
        if usage_scene:
            queryset = queryset.filter(usage_scenes__contains=[usage_scene])
        
        # ページネーション
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        paginator = Paginator(queryset, page_size)
        
        try:
            reviews_page = paginator.page(page)
        except:
            reviews_page = paginator.page(1)
        
        serializer = self.get_serializer(reviews_page.object_list, many=True)
        
        return Response({
            'success': True,
            'query': {
                'keyword': keyword,
                'store_name': store_name,
                'min_rating': min_rating,
                'usage_scene': usage_scene,
            },
            'page': page,
            'total_pages': paginator.num_pages,
            'total_results': paginator.count,
            'reviews': serializer.data
        })
    
    def update_store_ratings(self, store):
        """店舗の評価情報を更新"""
        reviews = DetailedReview.objects.filter(
            store=store,
            is_deleted=False,
            visibility='public'  # 公開レビューのみ
        )
        
        if reviews.exists():
            avg_rating = reviews.aggregate(
                avg=Avg('overall_rating')
            )['avg']
            reviews_count = reviews.count()
            
            # 店舗モデルの評価情報を更新
            store.rating = round(avg_rating, 1) if avg_rating else 0
            store.reviews_count = reviews_count
            store.save()
    
    def are_friends(self, user1, user2):
        """フレンド関係かチェック"""
        return Friendship.objects.filter(
            Q(from_user=user1, to_user=user2, status='accepted') |
            Q(from_user=user2, to_user=user1, status='accepted')
        ).exists()