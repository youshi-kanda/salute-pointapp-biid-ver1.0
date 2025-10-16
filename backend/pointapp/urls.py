from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from core.test_views import PartnerAPITestView, api_status, get_totp
from core import fincode_views
from core.custom_admin import custom_admin_site

def health(_request):  # フロント互換のヘルスエンドポイント
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('admin/', custom_admin_site.urls),  # カスタムAdmin（ログイン後にリダイレクト）
    path('production-admin/', include('core.production_admin_urls')),  # 本番管理画面
    path('api/', include('core.urls')),
    path('api/ec/', include('core.ec_point_urls')),  # EC購入ポイント付与システムAPI
    path('api/deposit/', include('core.deposit_urls')),  # デポジット管理API
    path('api/partner/', include('core.partner_urls')),
    path('api/fincode/', include('core.fincode_urls')),  # FINCODE決済API（統一）
    # 互換目的：POSTのAPPEND_SLASHが効かないケースのため両方受ける
    path('api/fincode/payment/initiate', fincode_views.initiate_payment, name='fincode_initiate_no_slash'),
    path('api/status/', api_status, name='api-status'),
    path('api/health/', health, name='api-health'),   # 追加: /api/health/
    path('api/get-totp/', get_totp, name='get-totp'),
    path('test/', PartnerAPITestView.as_view(), name='partner-api-test'),
    path('', PartnerAPITestView.as_view(), name='home'),
]
