from rest_framework import serializers
from decimal import Decimal
from .models import (
    APIAccessKey, DigitalGiftBrand, DigitalGiftPurchaseID, DigitalGiftPurchase, 
    DigitalGiftUsageLog, User
)
import re


class DigitalGiftBrandSerializer(serializers.ModelSerializer):
    """デジタルギフトブランド シリアライザ"""
    
    class Meta:
        model = DigitalGiftBrand
        fields = [
            'id', 'brand_code', 'brand_name', 'brand_name_en', 
            'description', 'logo_url', 'supported_prices', 
            'min_price', 'max_price', 'commission_rate', 
            'commission_tax_rate', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def to_representation(self, instance):
        """レスポンス形式をカスタマイズ"""
        data = super().to_representation(instance)
        
        # サンプル価格での購入コストを計算
        if instance.supported_prices:
            sample_price = instance.supported_prices[0]
            cost_info = instance.calculate_total_cost(sample_price)
            data['sample_cost'] = cost_info
        
        return data


# Legacy Brand serializer for backward compatibility
class BrandSerializer(DigitalGiftBrandSerializer):
    """レガシーブランドシリアライザー（後方互換性）"""
    
    class Meta:
        model = DigitalGiftBrand
        fields = ['brand_code', 'brand_name', 'description', 'logo_url', 'supported_prices']
    
    def to_representation(self, instance):
        return {
            'code': instance.brand_code,
            'name': instance.brand_name,
            'description': instance.description,
            'logo_url': instance.logo_url,
            'allowed_prices': instance.supported_prices
        }


class CreatePurchaseIDSerializer(serializers.Serializer):
    """購入ID作成 シリアライザ"""
    
    brand_code = serializers.CharField(max_length=50)
    price = serializers.IntegerField(min_value=1)
    design_code = serializers.CharField(max_length=50, default='default')
    video_message = serializers.CharField(max_length=500, allow_blank=True, default='')
    advertising_text = serializers.CharField(max_length=200, allow_blank=True, default='')
    
    def validate_brand_code(self, value):
        """ブランドコード検証"""
        try:
            brand = DigitalGiftBrand.objects.get(brand_code=value, is_active=True)
            self.context['brand'] = brand
            return value
        except DigitalGiftBrand.DoesNotExist:
            raise serializers.ValidationError(f"Brand '{value}' not found or inactive")
    
    def validate(self, attrs):
        """全体バリデーション"""
        brand = self.context.get('brand')
        price = attrs['price']
        
        if brand:
            # 価格範囲チェック
            if price < brand.min_price or price > brand.max_price:
                raise serializers.ValidationError(
                    f"Price {price} is out of range ({brand.min_price}-{brand.max_price})"
                )
            
            # サポート価格チェック
            if brand.supported_prices and price not in brand.supported_prices:
                raise serializers.ValidationError(
                    f"Price {price} is not supported for this brand. "
                    f"Supported prices: {brand.supported_prices}"
                )
        
        return attrs


# Legacy PurchaseIDCreateSerializer for backward compatibility
class PurchaseIDCreateSerializer(serializers.Serializer):
    """購入ID作成シリアライザー（レガシー）"""
    prices = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        help_text="購入IDに登録する金額のリスト"
    )
    name = serializers.CharField(
        max_length=255,
        help_text="購入したギフトの名前"
    )
    issuer = serializers.CharField(
        max_length=255,
        help_text="送付者名"
    )
    brands = serializers.ListField(
        child=serializers.CharField(max_length=50),
        min_length=1,
        help_text="掲載する交換先のリスト"
    )
    is_strict = serializers.BooleanField(
        help_text="組み合わせられないペアがある場合にリクエストを拒否するか"
    )
    
    def validate_brands(self, value):
        """ブランドコードの検証"""
        valid_brands = DigitalGiftBrand.objects.filter(
            brand_code__in=value,
            is_active=True
        ).values_list('brand_code', flat=True)
        
        invalid_brands = set(value) - set(valid_brands)
        if invalid_brands:
            raise serializers.ValidationError(
                f"Invalid brand codes: {', '.join(invalid_brands)}"
            )
        
        return value
    
    def validate(self, data):
        """価格とブランドの組み合わせ検証"""
        if data['is_strict']:
            prices = data['prices']
            brand_codes = data['brands']
            
            brands = DigitalGiftBrand.objects.filter(brand_code__in=brand_codes, is_active=True)
            
            for brand in brands:
                allowed_prices = brand.supported_prices
                invalid_prices = [p for p in prices if p not in allowed_prices]
                
                if invalid_prices:
                    raise serializers.ValidationError(
                        f"Brand '{brand.brand_code}' does not support prices: {invalid_prices}"
                    )
        
        return data


class PurchaseGiftSerializer(serializers.Serializer):
    """ギフト購入 シリアライザ"""
    
    purchase_id = serializers.CharField(max_length=100)
    request_id = serializers.CharField(max_length=100)
    
    def validate_purchase_id(self, value):
        """購入ID検証"""
        from django.utils import timezone
        
        try:
            purchase_id_obj = DigitalGiftPurchaseID.objects.get(
                purchase_id=value,
                expires_at__gt=timezone.now()
            )
            self.context['purchase_id_obj'] = purchase_id_obj
            return value
        except DigitalGiftPurchaseID.DoesNotExist:
            raise serializers.ValidationError("Purchase ID not found or expired")
    
    def validate_request_id(self, value):
        """リクエストID重複チェック"""
        if DigitalGiftPurchase.objects.filter(request_id=value).exists():
            raise serializers.ValidationError("Request ID already exists")
        return value


class DigitalGiftPurchaseSerializer(serializers.ModelSerializer):
    """デジタルギフト購入 シリアライザ"""
    
    brand_name = serializers.CharField(source='purchase_id_obj.brand.brand_name', read_only=True)
    brand_code = serializers.CharField(source='purchase_id_obj.brand.brand_code', read_only=True)
    price = serializers.IntegerField(source='purchase_id_obj.price', read_only=True)
    
    class Meta:
        model = DigitalGiftPurchase
        fields = [
            'id', 'request_id', 'gift_code', 'gift_url', 'pin_code',
            'status', 'expires_at', 'created_at', 'used_at',
            'brand_name', 'brand_code', 'price'
        ]
        read_only_fields = [
            'id', 'gift_code', 'gift_url', 'pin_code', 'status',
            'expires_at', 'created_at', 'used_at', 'brand_name', 
            'brand_code', 'price'
        ]


class PointToGiftExchangeSerializer(serializers.Serializer):
    """ポイント→ギフト交換 シリアライザ"""
    
    user_id = serializers.IntegerField()
    brand_code = serializers.CharField(max_length=50)
    price = serializers.IntegerField(min_value=1)
    design_code = serializers.CharField(max_length=50, default='default')
    video_message = serializers.CharField(max_length=500, allow_blank=True, default='')
    advertising_text = serializers.CharField(max_length=200, allow_blank=True, default='')
    
    def validate_user_id(self, value):
        """ユーザー検証"""
        try:
            user = User.objects.get(id=value, role='customer', is_active=True)
            self.context['user'] = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found or inactive")
    
    def validate_brand_code(self, value):
        """ブランドコード検証"""
        try:
            brand = DigitalGiftBrand.objects.get(brand_code=value, is_active=True)
            self.context['brand'] = brand
            return value
        except DigitalGiftBrand.DoesNotExist:
            raise serializers.ValidationError(f"Brand '{value}' not found or inactive")
    
    def validate(self, attrs):
        """全体バリデーション"""
        user = self.context.get('user')
        brand = self.context.get('brand')
        price = attrs['price']
        
        if user and brand:
            # ポイント残高チェック
            cost_info = brand.calculate_total_cost(price)
            required_points = cost_info['total']
            
            if user.point_balance < required_points:
                raise serializers.ValidationError(
                    f"Insufficient points. Required: {required_points}pt, "
                    f"Available: {user.point_balance}pt"
                )
            
            # 価格範囲チェック
            if price < brand.min_price or price > brand.max_price:
                raise serializers.ValidationError(
                    f"Price {price} is out of range ({brand.min_price}-{brand.max_price})"
                )
            
            # サポート価格チェック
            if brand.supported_prices and price not in brand.supported_prices:
                raise serializers.ValidationError(
                    f"Price {price} is not supported for this brand"
                )
        
        return attrs


# Legacy serializers for backward compatibility
class PurchaseIDSerializer(serializers.ModelSerializer):
    """購入ID詳細シリアライザー（レガシー）"""
    brands = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = DigitalGiftPurchaseID
        fields = [
            'id', 'price', 'purchase_id', 'brand_code', 'design_code', 
            'video_message', 'advertising_text', 'expires_at'
        ]
    
    def get_brands(self, obj):
        """ブランドコードのリストを返す"""
        return [obj.brand.brand_code] if obj.brand else []
    
    def get_color(self, obj):
        """配色情報を返す"""
        return {
            'main': 'ffffff',
            'sub': '000000'
        }
    
    def get_image(self, obj):
        """画像情報を返す"""
        return {
            'face': '',
            'header': ''
        }


class ColorSettingSerializer(serializers.Serializer):
    """配色設定シリアライザー"""
    main = serializers.RegexField(
        regex=r'^([a-fA-F0-9]{6})$',
        help_text="メイン配色（6桁のHEX）"
    )
    sub = serializers.RegexField(
        regex=r'^([a-fA-F0-9]{6})$',
        help_text="サブ配色（6桁のHEX）"
    )


class VideoSettingSerializer(serializers.Serializer):
    """動画設定シリアライザー"""
    url = serializers.URLField(
        help_text="YouTube動画のURL"
    )
    play_time = serializers.IntegerField(
        min_value=0,
        help_text="最低視聴秒数"
    )
    
    def validate_url(self, value):
        """YouTube URLの検証"""
        youtube_pattern = r'^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)'
        if not re.match(youtube_pattern, value):
            raise serializers.ValidationError("YouTube URLを指定してください")
        return value


class AdSettingSerializer(serializers.Serializer):
    """誘導枠設定シリアライザー"""
    redirect_url = serializers.URLField(
        help_text="誘導先URL"
    )


class GiftStatusSerializer(serializers.Serializer):
    """ギフト状態 シリアライザ"""
    
    request_id = serializers.CharField(max_length=100)
    status = serializers.CharField(max_length=20)
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    used_at = serializers.DateTimeField(allow_null=True)


class DigitalGiftUsageLogSerializer(serializers.ModelSerializer):
    """デジタルギフト使用ログ シリアライザ"""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    gift_info = serializers.SerializerMethodField()
    
    class Meta:
        model = DigitalGiftUsageLog
        fields = [
            'id', 'action', 'details', 'timestamp',
            'user_name', 'gift_info'
        ]
        read_only_fields = ['id', 'timestamp', 'user_name', 'gift_info']
    
    def get_gift_info(self, obj):
        """ギフト情報を取得"""
        try:
            gift = DigitalGiftPurchase.objects.get(id=obj.gift_id)
            return {
                'request_id': gift.request_id,
                'brand_code': gift.purchase_id_obj.brand.brand_code,
                'brand_name': gift.purchase_id_obj.brand.brand_name,
                'price': gift.purchase_id_obj.price,
                'status': gift.status
            }
        except DigitalGiftPurchase.DoesNotExist:
            return None


class GiftPurchaseCostSerializer(serializers.Serializer):
    """ギフト購入コスト計算 シリアライザ"""
    
    brand_code = serializers.CharField(max_length=50)
    price = serializers.IntegerField(min_value=1)
    
    def validate_brand_code(self, value):
        """ブランドコード検証"""
        try:
            brand = DigitalGiftBrand.objects.get(brand_code=value, is_active=True)
            self.context['brand'] = brand
            return value
        except DigitalGiftBrand.DoesNotExist:
            raise serializers.ValidationError(f"Brand '{value}' not found or inactive")
    
    def validate(self, attrs):
        """価格検証"""
        brand = self.context.get('brand')
        price = attrs['price']
        
        if brand:
            # 価格範囲チェック
            if price < brand.min_price or price > brand.max_price:
                raise serializers.ValidationError(
                    f"Price {price} is out of range ({brand.min_price}-{brand.max_price})"
                )
            
            # サポート価格チェック  
            if brand.supported_prices and price not in brand.supported_prices:
                raise serializers.ValidationError(
                    f"Price {price} is not supported for this brand"
                )
        
        return attrs


class ErrorResponseSerializer(serializers.Serializer):
    """エラーレスポンス シリアライザ"""
    
    error = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField(required=False)


# Legacy serializers for backward compatibility
class GiftPurchaseRequestSerializer(serializers.Serializer):
    """ギフト購入リクエストシリアライザー（レガシー）"""
    price = serializers.IntegerField(
        min_value=1,
        help_text="購入するギフトの金額"
    )
    
    def validate_price(self, value):
        """価格が購入IDに含まれているかチェック"""
        purchase_id = self.context.get('purchase_id')
        if purchase_id and hasattr(purchase_id, 'price') and value != purchase_id.price:
            raise serializers.ValidationError(
                f"Price {value} is not available for this purchase ID"
            )
        return value


class GiftPurchaseResponseSerializer(serializers.ModelSerializer):
    """ギフト購入レスポンスシリアライザー（レガシー）"""
    request = serializers.SerializerMethodField()
    gift = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    errors = serializers.SerializerMethodField()
    
    class Meta:
        model = DigitalGiftPurchase
        fields = ['request', 'gift', 'payment', 'errors']
    
    def get_request(self, obj):
        """リクエスト情報"""
        return {
            'id': obj.request_id,
            'payload': {}
        }
    
    def get_gift(self, obj):
        """ギフト情報"""
        return {
            'code': obj.gift_code,
            'url': obj.gift_url,
            'price': obj.purchase_id_obj.price,
            'expire_at': obj.expires_at.isoformat()
        }
    
    def get_payment(self, obj):
        """支払い情報"""
        cost_info = obj.purchase_id_obj.brand.calculate_total_cost(obj.purchase_id_obj.price)
        return {
            'total': float(cost_info['total']),
            'price': obj.purchase_id_obj.price,
            'commission': float(cost_info['commission']),
            'commission_tax': float(cost_info['commission_tax']),
            'currency': cost_info['currency']
        }
    
    def get_errors(self, obj):
        """エラー情報"""
        return []


class GiftPurchaseDetailSerializer(serializers.ModelSerializer):
    """購入済みギフト詳細シリアライザー（レガシー）"""
    request = serializers.SerializerMethodField()
    gift = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    
    class Meta:
        model = DigitalGiftPurchase
        fields = ['request', 'gift', 'payment']
    
    def get_request(self, obj):
        """リクエスト情報"""
        return {
            'id': obj.request_id,
            'payload': {}
        }
    
    def get_gift(self, obj):
        """ギフト情報"""
        return {
            'code': obj.gift_code,
            'url': obj.gift_url,
            'price': obj.purchase_id_obj.price,
            'expire_at': obj.expires_at.isoformat(),
            'status': obj.status
        }
    
    def get_payment(self, obj):
        """支払い情報"""
        cost_info = obj.purchase_id_obj.brand.calculate_total_cost(obj.purchase_id_obj.price)
        return {
            'total': float(cost_info['total']),
            'price': obj.purchase_id_obj.price,
            'commission': float(cost_info['commission']),
            'commission_tax': float(cost_info['commission_tax']),
            'currency': cost_info['currency']
        }