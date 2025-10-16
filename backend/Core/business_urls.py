from django.urls import path, include
from . import business_views

urlpatterns = [
    # === ポイント有効期限管理 ===
    path('api/user/points/detail/', business_views.user_points_detail, name='user_points_detail'),
    
    # === ポイント転送機能 ===
    path('api/user/points/transfer/', business_views.transfer_points, name='transfer_points'),
    path('api/user/points/transfer/history/', business_views.transfer_history, name='transfer_history'),
    
    # === 通知機能 ===
    path('api/user/notifications/', business_views.notifications, name='notifications'),
    path('api/user/notifications/<int:notification_id>/read/', business_views.mark_notification_read, name='mark_notification_read'),
    
    # === ポイント払戻し申請・管理機能 ===
    path('api/user/refund/request/', business_views.create_refund_request, name='create_refund_request'),
    path('api/user/refund/requests/', business_views.refund_requests, name='refund_requests'),
    
    # === 管理者用払戻し管理 ===
    path('api/admin/refund/requests/', business_views.admin_refund_requests, name='admin_refund_requests'),
    path('api/admin/refund/requests/<int:request_id>/process/', business_views.process_refund_request, name='process_refund_request'),
    
    # === ブログテーマ機能 ===
    path('api/blog/themes/', business_views.blog_themes, name='blog_themes'),
    path('api/blog/themes/<int:theme_id>/purchase/', business_views.purchase_blog_theme, name='purchase_blog_theme'),
    path('api/user/blog/themes/', business_views.user_blog_themes, name='user_blog_themes'),
    
    # === エリア展開制限機能 ===
    path('api/areas/', business_views.areas_list, name='areas_list'),
    path('api/stores/', business_views.stores_by_area, name='stores_by_area'),
    
    # === 管理者用エリア管理 ===
    path('api/admin/areas/', business_views.admin_areas_manage, name='admin_areas_manage'),
    path('api/admin/areas/<int:area_id>/', business_views.admin_area_detail, name='admin_area_detail'),
    
    # === メール通知管理機能 ===
    path('api/admin/email/templates/', business_views.admin_email_templates, name='admin_email_templates'),
    path('api/admin/email/templates/<int:template_id>/', business_views.admin_email_template_detail, name='admin_email_template_detail'),
    path('api/admin/email/logs/', business_views.admin_email_logs, name='admin_email_logs'),
    path('api/admin/email/retry/', business_views.admin_retry_failed_emails, name='admin_retry_failed_emails'),
    path('api/admin/email/test/', business_views.admin_send_test_email, name='admin_send_test_email'),
    
    # === デポジット管理機能 ===
    path('api/', include('core.deposit_urls')),
    
    # === 店舗決済機能 ===
    path('api/', include('core.store_payment_urls')),
]