"""
本番用運営管理画面URL設定
"""

from django.urls import path
from . import production_admin_views

app_name = 'production_admin'

urlpatterns = [
    # メインダッシュボード
    path('', production_admin_views.production_dashboard, name='dashboard'),
    
    # システム設定（スクリーンショット対応）
    path('settings/', production_admin_views.system_settings_view, name='system_settings'),
    
    # 管理画面
    path('users/', production_admin_views.user_management, name='users'),
    path('stores/', production_admin_views.store_management, name='stores'),
    path('transactions/', production_admin_views.transaction_management, name='transactions'),
    
    # API
    path('api/status/', production_admin_views.api_status, name='api_status'),
    path('api/point-pricing/', production_admin_views.point_pricing_settings, name='point_pricing_settings'),
]