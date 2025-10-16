from rest_framework import generics, status
from rest_framework.decorators import parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from datetime import timedelta
import hashlib
import secrets
import os

from .models import (
    DigitalGiftBrand, DigitalGiftPurchaseID, DigitalGiftPurchase, 
    DigitalGiftUsageLog, User
)
from .partner_serializers import (
    DigitalGiftBrandSerializer, CreatePurchaseIDSerializer, PurchaseGiftSerializer,
    DigitalGiftPurchaseSerializer, PointToGiftExchangeSerializer,
    GiftStatusSerializer, GiftPurchaseCostSerializer, ErrorResponseSerializer,
    # Legacy serializers for backward compatibility
    BrandSerializer, PurchaseIDCreateSerializer, PurchaseIDSerializer,
    ColorSettingSerializer, VideoSettingSerializer, AdSettingSerializer,
    GiftPurchaseRequestSerializer, GiftPurchaseResponseSerializer,
    GiftPurchaseDetailSerializer
)
from .partner_auth import PartnerAPIAuthMixin
from .digital_gift_client import get_digital_gift_client, DigitalGiftAPIError
from .point_service import PointService
import uuid
import logging

logger = logging.getLogger(__name__)


# New Digital Gift API Views
class DigitalGiftBrandListView(PartnerAPIAuthMixin, APIView):
    """デジタルギフトブランド一覧取得API"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """GET /api/partner/digital-gifts/brands"""
        try:
            # データベースからブランド一覧を取得
            brands = DigitalGiftBrand.objects.filter(is_active=True).order_by('brand_name')
            
            # 最新データが必要な場合は、APIから同期
            if request.GET.get('sync') == 'true':
                try:
                    client = get_digital_gift_client()
                    client.get_brands()  # これによりDBが更新される
                    brands = DigitalGiftBrand.objects.filter(is_active=True).order_by('brand_name')
                except Exception as e:
                    logger.warning(f"Failed to sync brands from API: {e}")
            
            serializer = DigitalGiftBrandSerializer(brands, many=True)
            return Response({
                'brands': serializer.data,
                'count': brands.count()
            })
            
        except Exception as e:
            logger.error(f"Failed to get brands: {e}")
            return Response({
                'error': 'internal_error',
                'message': 'Failed to retrieve brands'
            }, status=500)


class DigitalGiftPurchaseIDCreateView(PartnerAPIAuthMixin, APIView):
    """デジタルギフト購入ID作成API"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """POST /api/partner/digital-gifts/purchase-id"""
        try:
            serializer = CreatePurchaseIDSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'validation_error',
                    'message': 'Invalid request data',
                    'details': serializer.errors
                }, status=400)
            
            # デジタルギフトAPIクライアントを取得
            client = get_digital_gift_client()
            
            # 購入IDを作成
            response_data = client.create_purchase_id(
                brand_code=serializer.validated_data['brand_code'],
                price=serializer.validated_data['price'],
                design_code=serializer.validated_data.get('design_code', 'default'),
                video_message=serializer.validated_data.get('video_message', ''),
                advertising_text=serializer.validated_data.get('advertising_text', '')
            )
            
            return Response({
                'purchase_id': response_data['purchase_id'],
                'expires_at': response_data.get('expires_at'),
                'brand_code': serializer.validated_data['brand_code'],
                'price': serializer.validated_data['price']
            })
            
        except DigitalGiftAPIError as e:
            return Response({
                'error': 'digital_gift_api_error',
                'message': e.message,
                'details': e.response_data
            }, status=e.status_code or 500)
        except Exception as e:
            logger.error(f"Failed to create purchase ID: {e}")
            return Response({
                'error': 'internal_error',
                'message': 'Failed to create purchase ID'
            }, status=500)


class DigitalGiftPurchaseView(PartnerAPIAuthMixin, APIView):
    """デジタルギフト購入API"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """POST /api/partner/digital-gifts/purchase"""
        try:
            serializer = PurchaseGiftSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'validation_error',
                    'message': 'Invalid request data',
                    'details': serializer.errors
                }, status=400)
            
            # デジタルギフトAPIクライアントを取得
            client = get_digital_gift_client()
            
            # ギフトを購入
            with transaction.atomic():
                response_data = client.purchase_gift(
                    purchase_id=serializer.validated_data['purchase_id'],
                    request_id=serializer.validated_data['request_id']
                )
            
            return Response(response_data)
            
        except DigitalGiftAPIError as e:
            return Response({
                'error': 'digital_gift_api_error',
                'message': e.message,
                'details': e.response_data
            }, status=e.status_code or 500)
        except Exception as e:
            logger.error(f"Failed to purchase gift: {e}")
            return Response({
                'error': 'internal_error',
                'message': 'Failed to purchase gift'
            }, status=500)


class PointToGiftExchangeView(PartnerAPIAuthMixin, APIView):
    """ポイント→デジタルギフト交換API"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """POST /api/partner/digital-gifts/exchange"""
        try:
            serializer = PointToGiftExchangeSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'validation_error',
                    'message': 'Invalid request data',
                    'details': serializer.errors
                }, status=400)
            
            user = serializer.context['user']
            brand = serializer.context['brand']
            price = serializer.validated_data['price']
            
            # 購入コストを計算
            cost_info = brand.calculate_total_cost(price)
            required_points = cost_info['total']
            
            with transaction.atomic():
                # ポイントサービスを使用してポイント消費
                point_service = PointService(user)
                point_service.consume_points(
                    points=required_points,
                    description=f"デジタルギフト交換: {brand.brand_name} {price}円"
                )
                
                # デジタルギフトAPIクライアントを取得
                client = get_digital_gift_client()
                
                # 購入IDを作成
                purchase_id_response = client.create_purchase_id(
                    brand_code=serializer.validated_data['brand_code'],
                    price=price,
                    design_code=serializer.validated_data.get('design_code', 'default'),
                    video_message=serializer.validated_data.get('video_message', ''),
                    advertising_text=serializer.validated_data.get('advertising_text', '')
                )
                
                # ギフトを購入
                request_id = f"pt-{user.id}-{int(timezone.now().timestamp())}-{uuid.uuid4().hex[:8]}"
                gift_response = client.purchase_gift(
                    purchase_id=purchase_id_response['purchase_id'],
                    request_id=request_id
                )
                
                # 使用ログを記録
                client.log_gift_usage(
                    gift_id=gift_response['gift_id'],
                    user_id=user.id,
                    action='point_exchange',
                    details={
                        'points_consumed': required_points,
                        'brand_code': brand.brand_code,
                        'price': price,
                        'cost_breakdown': cost_info
                    }
                )
            
            return Response({
                'success': True,
                'gift': gift_response,
                'points_consumed': required_points,
                'remaining_points': user.point_balance
            })
            
        except ValueError as e:
            return Response({
                'error': 'insufficient_points',
                'message': str(e)
            }, status=400)
        except DigitalGiftAPIError as e:
            return Response({
                'error': 'digital_gift_api_error',
                'message': e.message,
                'details': e.response_data
            }, status=e.status_code or 500)
        except Exception as e:
            logger.error(f"Failed to exchange points for gift: {e}")
            return Response({
                'error': 'internal_error',
                'message': 'Failed to exchange points for gift'
            }, status=500)


# Legacy API Views (for backward compatibility)
class BrandListView(PartnerAPIAuthMixin, APIView):
    """交換先一覧取得API（レガシー）"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """GET /api/partner/brands"""
        brands = DigitalGiftBrand.objects.filter(is_active=True)
        serializer = BrandSerializer(brands, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)


class PurchaseIDCreateView(PartnerAPIAuthMixin, APIView):
    """購入ID作成API"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """POST /api/partner/purchases"""
        # リクエストIDの重複チェック
        request_id = request.META.get('HTTP_X_REALPAY_GIFT_API_REQUEST_ID')
        if not request_id:
            return Response({
                'error': 'Missing request ID header'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            self.validate_request_id(request_id)
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_409_CONFLICT)
        
        # データ検証
        serializer = PurchaseIDCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Parameter validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 購入ID生成
            purchase_id = self._generate_purchase_id()
            
            # 購入IDレコード作成
            purchase = PurchaseID.objects.create(
                id=purchase_id,
                access_key=self.get_partner_access_key(),
                prices=serializer.validated_data['prices'],
                name=serializer.validated_data['name'],
                issuer=serializer.validated_data['issuer'],
                is_strict=serializer.validated_data['is_strict']
            )
            
            # ブランドの関連付け
            brands = Brand.objects.filter(
                code__in=serializer.validated_data['brands'],
                is_active=True
            )
            purchase.brands.set(brands)
            
            return Response({
                'purchase': {
                    'id': purchase.id
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Purchase ID creation failed: {str(e)}'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    def _generate_purchase_id(self):
        """購入ID生成"""
        while True:
            purchase_id = secrets.token_hex(20)
            if not PurchaseID.objects.filter(id=purchase_id).exists():
                return purchase_id


class PurchaseIDDetailView(PartnerAPIAuthMixin, APIView):
    """購入ID詳細取得API"""
    permission_classes = [AllowAny]
    
    def get(self, request, purchase_id):
        """GET /api/partner/purchases/{purchaseId}"""
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            serializer = PurchaseIDSerializer(purchase)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except PurchaseID.DoesNotExist:
            return Response({
                'error': 'Purchase ID not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PurchaseIDColorView(PartnerAPIAuthMixin, APIView):
    """購入ID配色設定API"""
    permission_classes = [AllowAny]
    
    def post(self, request, purchase_id):
        """POST /api/partner/purchases/{purchaseId}/color"""
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            serializer = ColorSettingSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'Parameter validation failed',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 配色設定を更新
            purchase.color_main = serializer.validated_data['main']
            purchase.color_sub = serializer.validated_data['sub']
            purchase.save()
            
            return Response({
                'main': purchase.color_main,
                'sub': purchase.color_sub
            }, status=status.HTTP_200_OK)
            
        except PurchaseID.DoesNotExist:
            return Response({
                'error': 'Purchase ID not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PurchaseIDImageView(PartnerAPIAuthMixin, APIView):
    """購入ID画像設定API"""
    permission_classes = [AllowAny]
    
    @parser_classes([MultiPartParser, FormParser])
    def post(self, request, purchase_id, image_type):
        """POST /api/partner/purchases/{purchaseId}/image/{imageType}"""
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            # 画像ファイルの取得
            image_file = request.FILES.get('content')
            if not image_file:
                return Response({
                    'error': 'Image file is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ファイルサイズチェック
            if image_file.size > 2048 * 1024:  # 2MB
                return Response({
                    'error': 'File size exceeds 2MB limit'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ファイル拡張子チェック
            allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif']
            file_extension = os.path.splitext(image_file.name)[1].lower()
            if file_extension not in allowed_extensions:
                return Response({
                    'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ファイル保存
            filename = f"partner_images/{purchase_id}_{image_type}_{secrets.token_hex(8)}{file_extension}"
            file_path = default_storage.save(filename, ContentFile(image_file.read()))
            file_url = default_storage.url(file_path)
            
            # 購入IDに画像URLを設定
            if image_type == 'face':
                purchase.face_image_url = file_url
            elif image_type == 'header':
                purchase.header_image_url = file_url
            else:
                return Response({
                    'error': 'Invalid image type'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            purchase.save()
            
            return Response({
                'url': file_url
            }, status=status.HTTP_200_OK)
            
        except PurchaseID.DoesNotExist:
            return Response({
                'error': 'Purchase ID not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, purchase_id, image_type):
        """DELETE /api/partner/purchases/{purchaseId}/image/{imageType}"""
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            # 画像URLを削除
            if image_type == 'face':
                purchase.face_image_url = ''
            elif image_type == 'header':
                purchase.header_image_url = ''
            else:
                return Response({
                    'error': 'Invalid image type'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            purchase.save()
            
            return Response({}, status=status.HTTP_200_OK)
            
        except PurchaseID.DoesNotExist:
            return Response({
                'error': 'Purchase ID not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PurchaseIDVideoView(PartnerAPIAuthMixin, APIView):
    """購入ID動画設定API"""
    permission_classes = [AllowAny]
    
    def post(self, request, purchase_id):
        """POST /api/partner/purchases/{purchaseId}/video"""
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            serializer = VideoSettingSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'Parameter validation failed',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 動画設定を更新
            purchase.video_url = serializer.validated_data['url']
            purchase.video_play_time = serializer.validated_data['play_time']
            purchase.save()
            
            return Response({
                'url': purchase.video_url,
                'play_time': purchase.video_play_time
            }, status=status.HTTP_200_OK)
            
        except PurchaseID.DoesNotExist:
            return Response({
                'error': 'Purchase ID not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PurchaseIDAdView(PartnerAPIAuthMixin, APIView):
    """購入ID誘導枠設定API"""
    permission_classes = [AllowAny]
    
    @parser_classes([MultiPartParser, FormParser])
    def post(self, request, purchase_id):
        """POST /api/partner/purchases/{purchaseId}/ad"""
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            # 画像ファイルの取得
            image_file = request.FILES.get('image')
            redirect_url = request.data.get('redirect_url')
            
            if not image_file or not redirect_url:
                return Response({
                    'error': 'Image file and redirect URL are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ファイルサイズチェック
            if image_file.size > 2048 * 1024:  # 2MB
                return Response({
                    'error': 'File size exceeds 2MB limit'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ファイル保存
            filename = f"partner_ads/{purchase_id}_{secrets.token_hex(8)}.{image_file.name.split('.')[-1]}"
            file_path = default_storage.save(filename, ContentFile(image_file.read()))
            file_url = default_storage.url(file_path)
            
            # 誘導枠設定を更新
            purchase.ad_image_url = file_url
            purchase.ad_redirect_url = redirect_url
            purchase.save()
            
            return Response({
                'image': file_url,
                'redirect_url': redirect_url
            }, status=status.HTTP_200_OK)
            
        except PurchaseID.DoesNotExist:
            return Response({
                'error': 'Purchase ID not found'
            }, status=status.HTTP_404_NOT_FOUND)


class GiftPurchaseView(PartnerAPIAuthMixin, APIView):
    """ギフト購入API"""
    permission_classes = [AllowAny]
    
    def post(self, request, purchase_id):
        """POST /api/partner/purchases/{purchaseId}/gifts"""
        # リクエストIDの重複チェック
        request_id = request.META.get('HTTP_X_REALPAY_GIFT_API_REQUEST_ID')
        if not request_id:
            return Response({
                'error': 'Missing request ID header'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            self.validate_request_id(request_id)
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_409_CONFLICT)
        
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            serializer = GiftPurchaseRequestSerializer(
                data=request.data,
                context={'purchase_id': purchase}
            )
            if not serializer.is_valid():
                return Response({
                    'error': 'Parameter validation failed',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ギフト購入処理
            gift_purchase = self._create_gift_purchase(
                request_id, purchase, serializer.validated_data['price']
            )
            
            serializer = GiftPurchaseResponseSerializer(gift_purchase)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except PurchaseID.DoesNotExist:
            return Response({
                'error': 'Purchase ID not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Gift purchase failed: {str(e)}'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    def get(self, request, purchase_id):
        """GET /api/partner/purchases/{purchaseId}/gifts"""
        request_id = request.GET.get('request_id')
        if not request_id:
            return Response({
                'error': 'Missing request_id parameter'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            purchase = PurchaseID.objects.get(
                id=purchase_id,
                access_key=self.get_partner_access_key()
            )
            
            gift_purchase = GiftPurchase.objects.get(
                purchase_id=purchase,
                request_id=request_id
            )
            
            serializer = GiftPurchaseDetailSerializer(gift_purchase)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except (PurchaseID.DoesNotExist, GiftPurchase.DoesNotExist):
            return Response({
                'error': 'Gift purchase not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def _create_gift_purchase(self, request_id, purchase, price):
        """ギフト購入処理"""
        # 手数料計算
        commission = price * 0.05  # 5%手数料
        commission_tax = commission * 0.1  # 10%税
        total_amount = price + commission + commission_tax
        
        # ギフトコード生成
        gift_code = self._generate_gift_code()
        
        # ギフトURL生成
        gift_url = f"https://digital-gift.jp/user?code={gift_code}"
        
        # 有効期限設定（1年後）
        expires_at = timezone.now() + timedelta(days=365)
        
        # ギフト購入レコード作成
        gift_purchase = GiftPurchase.objects.create(
            request_id=request_id,
            purchase_id=purchase,
            gift_code=gift_code,
            gift_url=gift_url,
            price=price,
            total_amount=total_amount,
            commission=commission,
            commission_tax=commission_tax,
            expires_at=expires_at,
            status='completed'
        )
        
        return gift_purchase
    
    def _generate_gift_code(self):
        """ギフトコード生成"""
        while True:
            gift_code = secrets.token_hex(13)  # 26文字
            if not GiftPurchase.objects.filter(gift_code=gift_code).exists():
                return gift_code