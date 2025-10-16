from django.urls import path
from . import ec_point_views

urlpatterns = [
    # === ユーザー向けAPI ===
    # レシートアップロード
    path('receipt/upload/', ec_point_views.upload_receipt, name='upload_receipt'),
    
    # ユーザーの申請履歴
    path('user/requests/', ec_point_views.get_user_requests, name='user_ec_requests'),
    path('user/requests/<int:request_id>/', ec_point_views.get_request_detail, name='user_request_detail'),
    
    # === Webhook API ===
    # 店舗からの購入通知受信（GET方式で簡単実装）
    path('webhook/purchase/', ec_point_views.webhook_purchase, name='webhook_purchase'),
    
    # === 店舗管理者向けAPI ===
    # 承認待ち申請一覧
    path('store/pending-requests/', ec_point_views.get_store_pending_requests, name='store_pending_requests'),
    
    # 申請承認・拒否処理
    path('store/requests/<int:request_id>/approve/', ec_point_views.process_store_approval, name='process_store_approval'),
    
    # === 運営管理者向けAPI ===
    # 全申請管理
    path('admin/requests/', ec_point_views.ECRequestManagementView.as_view(), name='admin_ec_requests'),
    path('admin/requests/<int:request_id>/', ec_point_views.get_request_detail, name='admin_request_detail'),
    
    # 分析ダッシュボード用API
    path('admin/analytics/daily-trend/', ec_point_views.get_analytics_daily_trend, name='analytics_daily_trend'),
    path('admin/analytics/store-performance/', ec_point_views.get_analytics_store_performance, name='analytics_store_performance'),
    path('admin/analytics/payment-analysis/', ec_point_views.get_analytics_payment_analysis, name='analytics_payment_analysis'),
]