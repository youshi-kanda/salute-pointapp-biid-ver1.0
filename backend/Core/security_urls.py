from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .security_views import SecurityManagementViewSet, ContentModerationViewSet

router = DefaultRouter()

# セキュリティ管理
router.register(r'security', SecurityManagementViewSet, basename='security')

# コンテンツモデレーション（管理者用）
router.register(r'moderation', ContentModerationViewSet, basename='moderation')

urlpatterns = [
    path('', include(router.urls)),
    
    # カスタムエンドポイント
    path('security/block/', SecurityManagementViewSet.as_view({'post': 'block_user'}), name='block-user'),
    path('security/unblock/', SecurityManagementViewSet.as_view({'post': 'unblock_user'}), name='unblock-user'),
    path('security/blocked/', SecurityManagementViewSet.as_view({'get': 'blocked_users'}), name='blocked-users'),
    path('security/logs/', SecurityManagementViewSet.as_view({'get': 'security_logs'}), name='security-logs'),
    path('security/report/', SecurityManagementViewSet.as_view({'post': 'report_content'}), name='report-content'),
    path('security/status/', SecurityManagementViewSet.as_view({'get': 'activity_status'}), name='activity-status'),
    
    # モデレーション
    path('moderation/statistics/', ContentModerationViewSet.as_view({'get': 'statistics'}), name='moderation-stats'),
    path('moderation/<int:pk>/assign/', ContentModerationViewSet.as_view({'post': 'assign_moderator'}), name='assign-moderator'),
    path('moderation/<int:pk>/review/', ContentModerationViewSet.as_view({'post': 'review_content'}), name='review-content'),
]