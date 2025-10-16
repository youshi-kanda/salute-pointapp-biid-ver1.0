from django.urls import path
from . import deposit_views

urlpatterns = [
    # デポジット残高・情報
    path('stores/<int:store_id>/deposit/balance/', deposit_views.get_deposit_balance, name='deposit-balance'),
    path('stores/<int:store_id>/deposit/transactions/', deposit_views.get_deposit_transactions, name='deposit-transactions'),
    path('stores/<int:store_id>/deposit/usage-logs/', deposit_views.get_usage_logs, name='deposit-usage-logs'),
    
    # デポジット操作
    path('stores/<int:store_id>/deposit/charge/', deposit_views.charge_deposit, name='deposit-charge'),
    path('stores/<int:store_id>/deposit/consume/', deposit_views.consume_deposit, name='deposit-consume'),
    
    # 自動チャージ管理
    path('stores/<int:store_id>/deposit/auto-charge/', deposit_views.manage_auto_charge, name='deposit-auto-charge'),
    
    # ECポイント専用デポジット管理
    path('stores/<int:store_id>/deposit/ec/balance/', deposit_views.get_ec_deposit_balance, name='ec-deposit-balance'),
    path('stores/<int:store_id>/deposit/ec/usage-logs/', deposit_views.get_ec_usage_logs, name='ec-deposit-usage-logs'),
]