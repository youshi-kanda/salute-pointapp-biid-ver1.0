from django.urls import path
from . import partner_views

urlpatterns = [
    # New Digital Gift API endpoints
    path('digital-gifts/brands/', partner_views.DigitalGiftBrandListView.as_view(), name='digital-gift-brands'),
    path('digital-gifts/purchase-id/', partner_views.DigitalGiftPurchaseIDCreateView.as_view(), name='digital-gift-purchase-id'),
    path('digital-gifts/purchase/', partner_views.DigitalGiftPurchaseView.as_view(), name='digital-gift-purchase'),
    path('digital-gifts/exchange/', partner_views.PointToGiftExchangeView.as_view(), name='point-gift-exchange'),
    
    # Legacy API endpoints (for backward compatibility)
    # 交換先一覧
    path('brands/', partner_views.BrandListView.as_view(), name='partner-brands'),
    
    # 購入ID管理
    path('purchases/', partner_views.PurchaseIDCreateView.as_view(), name='partner-purchase-create'),
    path('purchases/<str:purchase_id>/', partner_views.PurchaseIDDetailView.as_view(), name='partner-purchase-detail'),
    
    # 配色設定
    path('purchases/<str:purchase_id>/color/', partner_views.PurchaseIDColorView.as_view(), name='partner-purchase-color'),
    
    # 画像設定
    path('purchases/<str:purchase_id>/image/<str:image_type>/', partner_views.PurchaseIDImageView.as_view(), name='partner-purchase-image'),
    
    # 動画設定
    path('purchases/<str:purchase_id>/video/', partner_views.PurchaseIDVideoView.as_view(), name='partner-purchase-video'),
    
    # 誘導枠設定
    path('purchases/<str:purchase_id>/ad/', partner_views.PurchaseIDAdView.as_view(), name='partner-purchase-ad'),
    
    # ギフト購入
    path('purchases/<str:purchase_id>/gifts/', partner_views.GiftPurchaseView.as_view(), name='partner-gift-purchase'),
]