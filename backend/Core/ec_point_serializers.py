from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import hashlib
import re

from .models import (
    ECPointRequest, StoreWebhookKey, PointAwardLog, DuplicateDetection, 
    Store, User
)


class ECPointRequestSerializer(serializers.ModelSerializer):
    """ECポイント申請シリアライザー"""
    
    class Meta:
        model = ECPointRequest
        fields = [
            'id', 'request_type', 'user', 'store', 'purchase_amount', 'order_id',
            'purchase_date', 'receipt_image', 'receipt_description', 'status',
            'points_to_award', 'points_awarded', 'store_approved_at', 'store_approved_by',
            'rejection_reason', 'payment_method', 'payment_reference', 
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'status', 'points_to_award', 'points_awarded', 'store_approved_at',
            'store_approved_by', 'rejection_reason', 'payment_method', 'payment_reference',
            'created_at', 'updated_at', 'completed_at'
        ]
    
    def validate_purchase_amount(self, value):
        """購入金額の検証"""
        if value <= 0:
            raise serializers.ValidationError("購入金額は0円より大きい必要があります")
        if value > Decimal('1000000'):
            raise serializers.ValidationError("購入金額は1,000,000円以下である必要があります")
        return value
    
    def validate_order_id(self, value):
        """注文IDの検証"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("注文IDは必須です")
        
        # 英数字とハイフン、アンダースコアのみ許可
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            raise serializers.ValidationError("注文IDは英数字、ハイフン、アンダースコアのみ使用可能です")
        
        if len(value) > 100:
            raise serializers.ValidationError("注文IDは100文字以下である必要があります")
        
        return value.strip()
    
    def validate_receipt_image(self, value):
        """レシート画像の検証"""
        if self.initial_data.get('request_type') == 'receipt' and not value:
            raise serializers.ValidationError("レシート申請には画像が必要です")
        
        if value:
            # ファイルサイズチェック (5MB)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("画像ファイルのサイズは5MB以下である必要があります")
            
            # ファイル形式チェック
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(value, 'content_type') and value.content_type not in allowed_types:
                raise serializers.ValidationError("JPEG、PNG、GIF、WebP形式の画像のみアップロード可能です")
        
        return value
    
    def validate_purchase_date(self, value):
        """購入日時の検証"""
        if value > timezone.now():
            raise serializers.ValidationError("購入日時は現在時刻より前である必要があります")
        
        # 1年前より古い購入は拒否
        one_year_ago = timezone.now() - timezone.timedelta(days=365)
        if value < one_year_ago:
            raise serializers.ValidationError("1年以上前の購入は申請できません")
        
        return value
    
    def validate(self, attrs):
        """全体的な検証"""
        request_type = attrs.get('request_type')
        
        if request_type == 'receipt':
            # レシート申請の場合、必須フィールドをチェック
            if not attrs.get('receipt_image'):
                raise serializers.ValidationError({
                    'receipt_image': 'レシート申請には画像が必要です'
                })
        
        return attrs


class ReceiptUploadSerializer(serializers.Serializer):
    """レシートアップロード専用シリアライザー"""
    store_name = serializers.CharField(max_length=200, help_text="店舗名")
    purchase_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=Decimal('1'),
        max_value=Decimal('1000000'),
        help_text="購入金額"
    )
    order_id = serializers.CharField(max_length=100, help_text="注文番号")
    purchase_date = serializers.DateTimeField(help_text="購入日時")
    receipt_image = serializers.ImageField(help_text="レシート画像")
    receipt_description = serializers.CharField(
        max_length=1000, 
        required=False, 
        allow_blank=True,
        help_text="レシート詳細（オプション）"
    )
    
    def validate_store_name(self, value):
        """店舗名の検証と店舗オブジェクトの取得"""
        try:
            store = Store.objects.get(name__icontains=value.strip(), status='active')
            return store
        except Store.DoesNotExist:
            raise serializers.ValidationError(f"店舗「{value}」が見つかりません")
        except Store.MultipleObjectsReturned:
            raise serializers.ValidationError(f"複数の店舗がマッチしました。より具体的な店舗名を入力してください")
    
    def validate_order_id(self, value):
        """注文IDの重複チェック"""
        value = value.strip()
        
        if ECPointRequest.objects.filter(order_id=value).exists():
            raise serializers.ValidationError("この注文IDは既に申請済みです")
        
        return value
    
    def create(self, validated_data):
        """レシート申請を作成"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise ValidationError("認証が必要です")
        
        # store_nameは既にStoreオブジェクトに変換済み
        store = validated_data.pop('store_name')
        
        # リクエストハッシュ生成
        hash_data = f"{request.user.id}_{store.id}_{validated_data['order_id']}_{validated_data['purchase_amount']}_{validated_data['purchase_date']}"
        request_hash = hashlib.sha256(hash_data.encode()).hexdigest()
        
        # IPアドレス取得
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        ec_request = ECPointRequest.objects.create(
            request_type='receipt',
            user=request.user,
            store=store,
            purchase_amount=validated_data['purchase_amount'],
            order_id=validated_data['order_id'],
            purchase_date=validated_data['purchase_date'],
            receipt_image=validated_data['receipt_image'],
            receipt_description=validated_data.get('receipt_description', ''),
            request_hash=request_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            points_to_award=int(validated_data['purchase_amount'] // 100)  # 100円で1ポイント
        )
        
        return ec_request
    
    def get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


class WebhookRequestSerializer(serializers.Serializer):
    """Webhookリクエスト用シリアライザー"""
    user_id = serializers.IntegerField(help_text="ユーザーID")
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('1'),
        max_value=Decimal('1000000'),
        help_text="購入金額"
    )
    order_id = serializers.CharField(max_length=100, help_text="注文ID")
    store_key = serializers.CharField(max_length=64, help_text="店舗認証キー")
    purchase_date = serializers.DateTimeField(
        required=False,
        help_text="購入日時（省略時は現在時刻）"
    )
    
    def validate_user_id(self, value):
        """ユーザーIDの検証"""
        try:
            user = User.objects.get(id=value, role='customer', status='active')
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("有効なユーザーが見つかりません")
    
    def validate_store_key(self, value):
        """店舗キーの検証"""
        try:
            webhook_key = StoreWebhookKey.objects.get(
                webhook_key=value, 
                is_active=True,
                store__status='active'
            )
            return webhook_key
        except StoreWebhookKey.DoesNotExist:
            raise serializers.ValidationError("無効な店舗キーです")
    
    def validate_order_id(self, value):
        """注文IDの重複チェック"""
        if ECPointRequest.objects.filter(order_id=value.strip()).exists():
            raise serializers.ValidationError("この注文IDは既に処理済みです")
        return value.strip()
    
    def validate(self, attrs):
        """IPアドレス制限チェック"""
        request = self.context.get('request')
        if request:
            webhook_key = attrs.get('store_key')
            if webhook_key:
                client_ip = self.get_client_ip(request)
                if not webhook_key.is_ip_allowed(client_ip):
                    raise serializers.ValidationError("このIPアドレスからのアクセスは許可されていません")
        
        return attrs
    
    def get_client_ip(self, request):
        """クライアントIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


class StoreApprovalSerializer(serializers.Serializer):
    """店舗承認・拒否用シリアライザー"""
    action = serializers.ChoiceField(
        choices=[('approve', '承認'), ('reject', '拒否')],
        help_text="承認または拒否"
    )
    rejection_reason = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="拒否理由（拒否時必須）"
    )
    
    def validate(self, attrs):
        """拒否時の理由必須チェック"""
        if attrs.get('action') == 'reject' and not attrs.get('rejection_reason'):
            raise serializers.ValidationError({
                'rejection_reason': '拒否する場合は理由の入力が必要です'
            })
        return attrs


class PointAwardLogSerializer(serializers.ModelSerializer):
    """ポイント付与ログシリアライザー"""
    user_name = serializers.CharField(source='ec_request.user.username', read_only=True)
    store_name = serializers.CharField(source='ec_request.store.name', read_only=True)
    purchase_amount = serializers.DecimalField(source='ec_request.purchase_amount', max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = PointAwardLog
        fields = [
            'id', 'awarded_points', 'award_rate', 'processing_duration_ms',
            'created_at', 'user_name', 'store_name', 'purchase_amount'
        ]
        read_only_fields = fields


class DuplicateDetectionSerializer(serializers.ModelSerializer):
    """重複検知シリアライザー"""
    original_user = serializers.CharField(source='original_request.user.username', read_only=True)
    original_store = serializers.CharField(source='original_request.store.name', read_only=True)
    duplicate_user = serializers.CharField(source='duplicate_request.user.username', read_only=True)
    duplicate_store = serializers.CharField(source='duplicate_request.store.name', read_only=True)
    
    class Meta:
        model = DuplicateDetection
        fields = [
            'id', 'detection_type', 'severity', 'detection_details',
            'is_resolved', 'resolved_by', 'resolved_at', 'created_at',
            'original_user', 'original_store', 'duplicate_user', 'duplicate_store'
        ]
        read_only_fields = [
            'id', 'created_at', 'original_user', 'original_store', 
            'duplicate_user', 'duplicate_store'
        ]


class StoreWebhookKeySerializer(serializers.ModelSerializer):
    """店舗Webhookキーシリアライザー"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    
    class Meta:
        model = StoreWebhookKey
        fields = [
            'id', 'store', 'store_name', 'webhook_key', 'allowed_ips',
            'is_active', 'rate_limit_per_minute', 'last_used_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'store_name', 'webhook_key', 'last_used_at', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Webhookキーを生成して作成"""
        validated_data['webhook_key'] = StoreWebhookKey.generate_key()
        return super().create(validated_data)


class ECRequestListSerializer(serializers.ModelSerializer):
    """EC申請一覧用シリアライザー"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    has_receipt_image = serializers.SerializerMethodField()
    
    class Meta:
        model = ECPointRequest
        fields = [
            'id', 'request_type', 'request_type_display', 'user_name', 'user_email',
            'store_name', 'purchase_amount', 'order_id', 'purchase_date',
            'status', 'status_display', 'points_to_award', 'points_awarded',
            'store_approved_at', 'rejection_reason', 'created_at',
            'has_receipt_image'
        ]
    
    def get_has_receipt_image(self, obj):
        """レシート画像の有無"""
        return bool(obj.receipt_image)


class ECRequestDetailSerializer(serializers.ModelSerializer):
    """EC申請詳細用シリアライザー"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    approved_by_name = serializers.CharField(source='store_approved_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    
    class Meta:
        model = ECPointRequest
        fields = [
            'id', 'request_type', 'request_type_display', 'user_name', 'user_email',
            'store_name', 'purchase_amount', 'order_id', 'purchase_date',
            'receipt_image', 'receipt_description', 'status', 'status_display',
            'points_to_award', 'points_awarded', 'store_approved_at', 'approved_by_name',
            'rejection_reason', 'payment_method', 'payment_method_display', 
            'payment_reference', 'ip_address', 'created_at', 'updated_at', 'completed_at'
        ]