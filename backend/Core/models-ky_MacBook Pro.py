from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid


class AccountRank(models.Model):
    """アカウントランク設定"""
    name = models.CharField(max_length=50, unique=True)  # Bronze, Silver, Gold, Platinum
    points_threshold = models.IntegerField(default=0)  # ランク到達に必要なポイント
    daily_send_limit = models.IntegerField(default=1000)  # 1日送信上限
    monthly_send_limit = models.IntegerField(default=10000)  # 月間送信上限
    send_fee_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)  # 送信手数料率
    max_friends = models.IntegerField(default=100)  # 友達登録上限
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['points_threshold']

    def __str__(self):
        return f"{self.name} (≥{self.points_threshold}pt)"


class User(AbstractUser):
    member_id = models.CharField(max_length=50, unique=True)
    points = models.IntegerField(default=0)
    registration_date = models.DateTimeField(auto_now_add=True)
    last_login_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    location = models.CharField(max_length=255, blank=True)
    avatar = models.URLField(blank=True)
    account_rank = models.ForeignKey(AccountRank, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.member_id})"

    def get_current_rank(self):
        """現在のポイントに基づいてランクを取得"""
        if self.account_rank:
            return self.account_rank
        
        # ポイントに基づいて自動的にランクを決定
        rank = AccountRank.objects.filter(
            points_threshold__lte=self.points
        ).order_by('-points_threshold').first()
        
        if rank:
            self.account_rank = rank
            self.save()
            return rank
        
        return None


class Store(models.Model):
    CATEGORY_CHOICES = [
        ('restaurant', 'Restaurant'),
        ('retail', 'Retail'),
        ('service', 'Service'),
        ('entertainment', 'Entertainment'),
        ('health', 'Health'),
        ('education', 'Education'),
    ]
    
    PRICE_RANGE_CHOICES = [
        ('budget', 'Budget'),
        ('moderate', 'Moderate'),
        ('expensive', 'Expensive'),
        ('luxury', 'Luxury'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
    ]

    name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    registration_date = models.DateTimeField(auto_now_add=True)
    point_rate = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='restaurant')
    price_range = models.CharField(max_length=20, choices=PRICE_RANGE_CHOICES, default='moderate')
    features = models.JSONField(default=list, blank=True)
    specialties = models.JSONField(default=list, blank=True)
    
    rating = models.FloatField(default=0.0)
    reviews_count = models.IntegerField(default=0)
    hours = models.CharField(max_length=255, blank=True)
    biid_partner = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class PointTransaction(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('credit', 'Credit Card'),
        ('digital', 'Digital Payment'),
        ('bank', 'Bank Transfer'),
    ]
    
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='point_transactions')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='point_transactions')
    transaction_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    points_issued = models.IntegerField()
    transaction_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-transaction_date']

    def __str__(self):
        return f"{self.transaction_id} - {self.user.username} - {self.points_issued} points"


class GiftCategory(models.Model):
    """ギフトカテゴリ管理"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class Gift(models.Model):
    """ギフト商品管理"""
    GIFT_TYPE_CHOICES = [
        ('digital', 'デジタルギフト'),
        ('coupon', 'クーポン'),
        ('voucher', 'バウチャー'),
        ('physical', '現物商品'),
    ]
    
    STATUS_CHOICES = [
        ('active', '有効'),
        ('inactive', '無効'),
        ('sold_out', '売り切れ'),
        ('discontinued', '販売終了'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(GiftCategory, on_delete=models.CASCADE, related_name='gifts')
    gift_type = models.CharField(max_length=20, choices=GIFT_TYPE_CHOICES, default='digital')
    
    # 価格・在庫情報
    points_required = models.IntegerField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)
    unlimited_stock = models.BooleanField(default=False)
    
    # 画像・メディア
    image_url = models.URLField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    
    # 提供元情報
    provider_name = models.CharField(max_length=255)
    provider_url = models.URLField(blank=True)
    
    # ステータス・有効期限
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    
    # 使用条件
    usage_instructions = models.TextField(blank=True)
    terms_conditions = models.TextField(blank=True)
    
    # 統計情報
    exchange_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.points_required} pts)"
    
    def is_available(self):
        """ギフトが交換可能かチェック"""
        if self.status != 'active':
            return False
        
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        
        if not self.unlimited_stock and self.stock_quantity <= 0:
            return False
        
        return True


class GiftExchange(models.Model):
    """ギフト交換記録"""
    STATUS_CHOICES = [
        ('pending', '処理中'),
        ('completed', '完了'),
        ('failed', '失敗'),
        ('cancelled', 'キャンセル'),
        ('expired', '期限切れ'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gift_exchanges')
    gift = models.ForeignKey(Gift, on_delete=models.CASCADE, related_name='exchanges')
    
    # 交換情報
    points_spent = models.IntegerField()
    exchange_code = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # 配送・受取情報
    delivery_method = models.CharField(max_length=50, blank=True)
    delivery_address = models.TextField(blank=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    
    # デジタルギフト情報
    digital_code = models.CharField(max_length=500, blank=True)
    digital_url = models.URLField(blank=True)
    qr_code_url = models.URLField(blank=True)
    
    # 日時情報
    exchanged_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # 備考
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-exchanged_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.gift.name} - {self.status}"
    
    def generate_exchange_code(self):
        """交換コード生成"""
        import uuid
        import time
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"GFT-{timestamp}-{unique_id}"


class Friendship(models.Model):
    """友達関係"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('blocked', 'Blocked'),
    ]
    
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_sent')
    addressee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_received')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('requester', 'addressee')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.requester.username} → {self.addressee.username} ({self.status})"


class PointTransfer(models.Model):
    """ポイント送受信"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    transfer_id = models.CharField(max_length=50, unique=True, blank=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_sent')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_received')
    amount = models.IntegerField()
    fee = models.IntegerField(default=0)
    message = models.TextField(blank=True, max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # 日時情報
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # 通知情報
    sender_notified = models.BooleanField(default=False)
    receiver_notified = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.amount}pt ({self.status})"
    
    def save(self, *args, **kwargs):
        if not self.transfer_id:
            self.transfer_id = self.generate_transfer_id()
        super().save(*args, **kwargs)
    
    def generate_transfer_id(self):
        """送信ID生成"""
        import time
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"PT-{timestamp}-{unique_id}"
    
    def can_accept(self):
        """受け取り可能かチェック"""
        if self.status != 'pending':
            return False, "この送信は既に処理済みです"
        
        if timezone.now() > self.expires_at:
            return False, "送信が期限切れです"
        
        return True, ""
    
    def accept_transfer(self):
        """ポイント送信を受け取る"""
        can_accept, message = self.can_accept()
        if not can_accept:
            return False, message
        
        # ポイント移動
        self.receiver.points += self.amount
        self.receiver.save()
        
        # ステータス更新
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save()
        
        return True, "ポイントを受け取りました"


class Notification(models.Model):
    """通知システム"""
    TYPE_CHOICES = [
        ('friend_request', 'Friend Request'),
        ('friend_accepted', 'Friend Accepted'),
        ('point_received', 'Point Received'),
        ('point_accepted', 'Point Accepted'),
        ('point_declined', 'Point Declined'),
        ('gift_exchange', 'Gift Exchange'),
        ('system', 'System'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # 追加データ（ID等）
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title} ({'読了' if self.is_read else '未読'})"
