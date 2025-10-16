from rest_framework import serializers
from .models import (
    User, Store, PointTransaction, PaymentTransaction, Gift, GiftCategory, GiftExchange,
    UserPoint, PointTransfer, Notification, PromotionMail, AccountRank,
    RefundRequest, BlogTheme, UserBlogTheme, Area, EmailTemplate, EmailLog
)
# Social models imports - temporarily commented out due to model issues
# from .social_models import (
#     BlockedUser, SecurityLog, ContentModerationQueue,
#     Notification as SocialNotification, NotificationPreference
# )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'member_id', 'points', 'registration_date', 
                 'last_login_date', 'status', 'location', 'avatar']
        read_only_fields = ['id', 'registration_date']


class StoreSerializer(serializers.ModelSerializer):
    area_name = serializers.CharField(source='area.name', read_only=True)
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'owner_name', 'email', 'phone', 'address', 
                 'registration_date', 'point_rate', 'status', 'balance', 'monthly_fee',
                 'latitude', 'longitude', 'category', 'price_range', 'features', 
                 'specialties', 'rating', 'reviews_count', 'hours', 'biid_partner',
                 'area', 'area_name', 'deposit_balance', 'deposit_auto_charge', 
                 'deposit_auto_charge_amount']
        read_only_fields = ['id', 'registration_date']


class PointTransactionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    
    class Meta:
        model = PointTransaction
        fields = ['id', 'user', 'store', 'user_name', 'store_name', 'transaction_id', 
                 'amount', 'points_issued', 'transaction_date', 'payment_method', 
                 'status', 'description']
        read_only_fields = ['id', 'transaction_date']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.username', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'transaction_id', 'customer', 'store', 'customer_name', 'store_name',
            'transaction_type', 'payment_method', 'status', 'subtotal', 'tax_amount', 
            'total_amount', 'points_earned', 'points_used', 'points_balance_before',
            'points_balance_after', 'gmopg_order_id', 'gmopg_transaction_id',
            'external_payment_data', 'description', 'metadata', 'created_at',
            'updated_at', 'completed_at', 'receipt_number', 'receipt_generated',
            'receipt_emailed'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MemberSyncSerializer(serializers.Serializer):
    member_id = serializers.CharField(max_length=50)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=30, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    points = serializers.IntegerField(default=0)
    status = serializers.ChoiceField(
        choices=[('active', 'Active'), ('inactive', 'Inactive'), ('suspended', 'Suspended')],
        default='active'
    )
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    avatar = serializers.URLField(required=False, allow_blank=True)


class GiftCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftCategory
        fields = ['id', 'name', 'description', 'icon', 'is_active']


class GiftSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Gift
        fields = [
            'id', 'name', 'description', 'category', 'category_name', 'gift_type',
            'points_required', 'original_price', 'stock_quantity', 'unlimited_stock',
            'image_url', 'thumbnail_url', 'provider_name', 'provider_url',
            'status', 'available_from', 'available_until', 'usage_instructions',
            'terms_conditions', 'exchange_count', 'is_available', 'created_at'
        ]


class GiftExchangeSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    gift_name = serializers.CharField(source='gift.name', read_only=True)
    gift_image = serializers.URLField(source='gift.image_url', read_only=True)
    
    class Meta:
        model = GiftExchange
        fields = [
            'id', 'user', 'gift', 'user_name', 'gift_name', 'gift_image',
            'points_spent', 'exchange_code', 'status', 'delivery_method',
            'delivery_address', 'recipient_name', 'recipient_email', 'recipient_phone',
            'digital_code', 'digital_url', 'qr_code_url', 'exchanged_at',
            'processed_at', 'expires_at', 'used_at', 'notes'
        ]
        read_only_fields = ['exchange_code', 'exchanged_at']


class GiftExchangeRequestSerializer(serializers.Serializer):
    gift_id = serializers.IntegerField()
    delivery_method = serializers.CharField(max_length=50, required=False, allow_blank=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True)
    recipient_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    recipient_email = serializers.EmailField(required=False, allow_blank=True)
    recipient_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


# === 新機能用シリアライザー ===

class UserPointSerializer(serializers.ModelSerializer):
    """ユーザーポイント詳細"""
    source_transaction_id = serializers.CharField(source='source_transaction.transaction_id', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = UserPoint
        fields = ['id', 'points', 'expiry_date', 'source_transaction_id', 
                 'created_at', 'is_expired', 'is_valid']


class PointTransferSerializer(serializers.ModelSerializer):
    """ポイント転送"""
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    recipient_name = serializers.CharField(source='recipient.username', read_only=True)
    
    class Meta:
        model = PointTransfer
        fields = ['id', 'sender', 'recipient', 'sender_name', 'recipient_name',
                 'points', 'status', 'message', 'transfer_fee', 
                 'created_at', 'processed_at']


class NotificationSerializer(serializers.ModelSerializer):
    """通知"""
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'title', 'message', 'is_read',
                 'is_sent', 'email_sent', 'email_sent_at', 'priority', 
                 'created_at', 'read_at']


class PromotionMailSerializer(serializers.ModelSerializer):
    """プロモーションメール"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    target_area_name = serializers.CharField(source='target_area.name', read_only=True)
    
    class Meta:
        model = PromotionMail
        fields = ['id', 'store', 'store_name', 'title', 'content', 'target_area',
                 'target_area_name', 'target_user_rank', 'send_cost', 'recipients_count', 
                 'sent_count', 'status', 'scheduled_at', 'sent_at', 'created_at']


class AccountRankSerializer(serializers.ModelSerializer):
    """アカウントランク"""
    class Meta:
        model = AccountRank
        fields = ['rank', 'required_points', 'required_transactions', 
                 'point_multiplier', 'privileges']


class RefundRequestSerializer(serializers.ModelSerializer):
    """ポイント払戻し申請"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.username', read_only=True)
    
    class Meta:
        model = RefundRequest
        fields = ['id', 'user', 'user_name', 'points_to_refund', 'refund_amount',
                 'refund_type', 'status', 'reason', 'bank_name', 'branch_name',
                 'account_type', 'account_number', 'account_holder', 
                 'processed_by', 'processed_by_name', 'admin_notes', 
                 'processing_fee', 'requested_at', 'processed_at', 'completed_at']
        read_only_fields = ['refund_amount', 'processed_by', 'processed_at', 'completed_at']


class BlogThemeSerializer(serializers.ModelSerializer):
    """ブログテーマ"""
    class Meta:
        model = BlogTheme
        fields = ['id', 'name', 'description', 'primary_color', 'secondary_color',
                 'accent_color', 'background_color', 'text_color', 'font_family',
                 'font_size_base', 'layout_type', 'custom_css', 'is_active',
                 'is_premium', 'price', 'created_at']


class UserBlogThemeSerializer(serializers.ModelSerializer):
    """ユーザーブログテーマ"""
    theme_name = serializers.CharField(source='theme.name', read_only=True)
    theme_data = BlogThemeSerializer(source='theme', read_only=True)
    
    class Meta:
        model = UserBlogTheme
        fields = ['id', 'theme', 'theme_name', 'theme_data', 'purchased_at']


class AreaSerializer(serializers.ModelSerializer):
    """エリアマスタ"""
    stores_count = serializers.IntegerField(source='stores.count', read_only=True)
    
    class Meta:
        model = Area
        fields = ['id', 'name', 'display_order', 'is_active', 'stores_count', 'created_at', 'updated_at']


class EmailTemplateSerializer(serializers.ModelSerializer):
    """メールテンプレート"""
    class Meta:
        model = EmailTemplate
        fields = ['id', 'name', 'subject', 'body_html', 'body_text', 'description',
                 'available_variables', 'is_active', 'created_at', 'updated_at']


class EmailLogSerializer(serializers.ModelSerializer):
    """メール送信ログ"""
    notification_title = serializers.CharField(source='notification.title', read_only=True)
    
    class Meta:
        model = EmailLog
        fields = ['id', 'notification', 'notification_title', 'recipient_email', 
                 'subject', 'template_used', 'status', 'sent_at', 'error_message',
                 'retry_count', 'created_at']


# Socialシリアライザーは一時的に無効化（モデル依存問題のため）
# 実際のプロダクションでは、social_models.pyが完全に実装されてからこれらを有効化

class ReportContentSerializer(serializers.Serializer):
    """コンテンツ報告シリアライザー"""
    content_type = serializers.ChoiceField(choices=['post', 'comment', 'review'])
    content_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=[
        'spam', 'harassment', 'inappropriate', 'misinformation', 'copyright', 'other'
    ])
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
