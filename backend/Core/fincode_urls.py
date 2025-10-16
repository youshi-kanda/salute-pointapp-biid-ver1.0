# GMO FINCODE 決済 URL設定

from django.urls import path
from . import fincode_views

app_name = 'fincode'

urlpatterns = [
    # 決済API
    path('payment/initiate/', fincode_views.initiate_payment, name='initiate_payment'),
    path('payment/status/<str:payment_id>/', fincode_views.check_payment_status, name='check_payment_status'),
    path('payment/refund/<str:payment_id>/', fincode_views.refund_payment, name='refund_payment'),
    
    # 決済フロー用URL（リダイレクト）
    path('payment/return/<str:order_id>/', fincode_views.payment_return, name='payment_return'),
    path('payment/cancel/<str:order_id>/', fincode_views.payment_cancel, name='payment_cancel'),
    path('payment/notify/', fincode_views.payment_notify, name='payment_notify'),
    
    # モック決済ページ
    path('mock-payment/<str:order_id>/', fincode_views.mock_payment_page, name='mock_payment_page'),
    
    # 取引履歴
    path('transactions/', fincode_views.get_transaction_history, name='transaction_history'),
]