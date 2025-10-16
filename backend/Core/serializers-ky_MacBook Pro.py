from rest_framework import serializers
from django.db import models
from .models import (
    User, Store, PointTransaction, Gift, GiftCategory, GiftExchange,
    AccountRank, Friendship, PointTransfer, Notification
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'member_id', 'points', 'registration_date', 
                 'last_login_date', 'status', 'location', 'avatar']
        read_only_fields = ['id', 'registration_date']


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['id', 'name', 'owner_name', 'email', 'phone', 'address', 
                 'registration_date', 'point_rate', 'status', 'balance', 'monthly_fee',
                 'latitude', 'longitude', 'category', 'price_range', 'features', 
                 'specialties', 'rating', 'reviews_count', 'hours', 'biid_partner']
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


# === ユーザー間ポイント送受信関連シリアライザー ===

class AccountRankSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountRank
        fields = [
            'id', 'name', 'points_threshold', 'daily_send_limit', 
            'monthly_send_limit', 'send_fee_rate', 'max_friends',
            'created_at', 'updated_at'
        ]


class UserWithRankSerializer(serializers.ModelSerializer):
    account_rank = AccountRankSerializer(read_only=True)
    current_rank = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'member_id', 'points', 
            'registration_date', 'last_login_date', 'status', 
            'location', 'avatar', 'account_rank', 'current_rank'
        ]
        read_only_fields = ['id', 'registration_date']
    
    def get_current_rank(self, obj):
        rank = obj.get_current_rank()
        return AccountRankSerializer(rank).data if rank else None


class FriendshipSerializer(serializers.ModelSerializer):
    requester_info = UserSerializer(source='requester', read_only=True)
    addressee_info = UserSerializer(source='addressee', read_only=True)
    
    class Meta:
        model = Friendship
        fields = [
            'id', 'requester', 'addressee', 'requester_info', 'addressee_info',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class FriendRequestSerializer(serializers.Serializer):
    user_identifier = serializers.CharField()  # member_id or username
    
    def validate_user_identifier(self, value):
        try:
            # member_idまたはusernameで検索
            user = User.objects.filter(
                models.Q(member_id=value) | models.Q(username=value)
            ).first()
            if not user:
                raise serializers.ValidationError("ユーザーが見つかりません")
            return user
        except Exception:
            raise serializers.ValidationError("無効なユーザー識別子です")


class PointTransferSerializer(serializers.ModelSerializer):
    sender_info = UserSerializer(source='sender', read_only=True)
    receiver_info = UserSerializer(source='receiver', read_only=True)
    total_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = PointTransfer
        fields = [
            'id', 'transfer_id', 'sender', 'receiver', 'sender_info', 'receiver_info',
            'amount', 'fee', 'total_amount', 'message', 'status',
            'created_at', 'accepted_at', 'expires_at',
            'sender_notified', 'receiver_notified'
        ]
        read_only_fields = ['transfer_id', 'created_at', 'accepted_at']
    
    def get_total_amount(self, obj):
        return obj.amount + obj.fee


class PointTransferRequestSerializer(serializers.Serializer):
    receiver_identifier = serializers.CharField()  # member_id or username
    amount = serializers.IntegerField(min_value=1)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_receiver_identifier(self, value):
        try:
            user = User.objects.filter(
                models.Q(member_id=value) | models.Q(username=value)
            ).first()
            if not user:
                raise serializers.ValidationError("受信者が見つかりません")
            return user
        except Exception:
            raise serializers.ValidationError("無効な受信者識別子です")


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'notification_type', 'title', 'message', 
            'data', 'is_read', 'created_at'
        ]
        read_only_fields = ['created_at']
