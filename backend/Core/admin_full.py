"""
BIID Point App 本番環境用 Django Admin 設定
全46モデルの包括的管理機能を提供
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum, Avg
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import (
    # ユーザー・認証関連
    User, AccountRank, APIAccessKey, Area,
    
    # 商品・ギフト関連  
    Gift, GiftCategory, GiftExchange, GiftPurchase,
    DigitalGiftBrand, DigitalGiftPurchase, DigitalGiftUsageLog, DigitalGiftPurchaseID,
    
    # 決済・金融関連
    PaymentTransaction, PaymentTransactionItem, PaymentLog, Receipt,
    DepositTransaction, DepositUsageLog, DepositAutoChargeRule,
    PointTransaction, PointTransfer, PointPurchaseTransaction, PointAwardLog, UserPoint,
    MonthlyBilling, RefundRequest,
    
    # 店舗関連
    Store, StoreConfiguration, StoreWebhookKey,
    
    # EC・外部連携
    ECPointRequest, MeltyRankConfiguration,
    
    # 通知・コミュニケーション
    Notification, EmailTemplate, EmailLog, PromotionMail,
    
    # セキュリティ・監査
    SecurityLog, AuditLog, APIRateLimit, DuplicateDetection,
    
    # ソーシャル機能 (必要に応じてインポート)
    # UserPrivacySettings, Friendship, SocialPost, SocialPostLike, 
    # SocialPostComment, SocialPostShare, UserBlock, DetailedReview, ReviewHelpful,
    
    # システム・その他
    BlogTheme, UserBlogTheme, Brand, PurchaseID
)


# ===== 基本設定 =====
class BaseAdmin(admin.ModelAdmin):
    """全Adminクラスの基底クラス"""
    save_as = True
    save_on_top = True


# ===== ユーザー・認証関連 =====
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'member_id', 'point_balance_display', 'rank', 'melty_linked_status', 'status', 'registration_date')
    list_filter = ('status', 'rank', 'registration_source', 'is_melty_linked', 'registration_date', 'last_login_date')
    search_fields = ('username', 'email', 'member_id')
    date_hierarchy = 'registration_date'
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('BIID Point System', {
            'fields': ('member_id', 'rank', 'point_balance', 'status', 'location', 'avatar')
        }),
        ('MELTY Integration', {
            'fields': ('is_melty_linked', 'melty_user_id', 'melty_email', 'melty_connected_at', 'registration_source'),
            'classes': ('collapse',)
        }),
        ('Social Features', {
            'fields': ('unlocked_social_skins', 'bio', 'birth_date', 'gender', 'website'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = BaseUserAdmin.readonly_fields + ('melty_connected_at', 'registration_date')
    
    actions = ['reset_melty_link', 'upgrade_to_silver', 'upgrade_to_gold', 'suspend_users', 'activate_users']
    
    def point_balance_display(self, obj):
        return f"{obj.point_balance:,}pt"
    point_balance_display.short_description = 'ポイント残高'
    
    def melty_linked_status(self, obj):
        if obj.is_melty_linked:
            return format_html('<span style="color: green;">✓ 連携済み</span>')
        return format_html('<span style="color: red;">× 未連携</span>')
    melty_linked_status.short_description = 'MELTY連携'
    
    # カスタムアクション
    def reset_melty_link(self, request, queryset):
        count = queryset.filter(is_melty_linked=True).update(
            is_melty_linked=False, melty_user_id=None, melty_email=None
        )
        self.message_user(request, f'{count}件のMELTY連携をリセットしました。')
    
    def suspend_users(self, request, queryset):
        count = queryset.update(status='suspended')
        self.message_user(request, f'{count}件のユーザーを停止しました。')
    
    def activate_users(self, request, queryset):
        count = queryset.update(status='active')
        self.message_user(request, f'{count}件のユーザーを有効化しました。')


@admin.register(AccountRank)
class AccountRankAdmin(BaseAdmin):
    list_display = ('rank', 'required_points', 'required_transactions', 'point_multiplier', 'user_count')
    list_filter = ('rank',)
    ordering = ['required_points']
    
    def user_count(self, obj):
        return User.objects.filter(rank=obj.rank).count()
    user_count.short_description = '該当ユーザー数'


@admin.register(APIAccessKey)
class APIAccessKeyAdmin(BaseAdmin):
    list_display = ('name', 'key_prefix', 'store', 'is_active', 'created_at', 'last_used_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'store__name')
    readonly_fields = ('key', 'created_at', 'last_used_at')
    
    def key_prefix(self, obj):
        return f"{obj.key[:8]}..." if obj.key else "未生成"
    key_prefix.short_description = 'APIキー'


# ===== 店舗関連 =====
@admin.register(Store)
class StoreAdmin(BaseAdmin):
    list_display = ('name', 'owner_name', 'category', 'status', 'point_rate', 'payment_total', 'registration_date')
    list_filter = ('status', 'category', 'price_range', 'biid_partner', 'registration_date')
    search_fields = ('name', 'owner_name', 'email')
    date_hierarchy = 'registration_date'
    readonly_fields = ('registration_date',)
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'owner_name', 'email', 'phone', 'address')
        }),
        ('ビジネス設定', {
            'fields': ('category', 'price_range', 'description', 'website')
        }),
        ('BIID設定', {
            'fields': ('status', 'point_rate', 'biid_partner')
        }),
    )
    
    def payment_total(self, obj):
        total = PaymentTransaction.objects.filter(store=obj, status='completed').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        return f"¥{total:,}"
    payment_total.short_description = '総売上'


@admin.register(StoreConfiguration)
class StoreConfigurationAdmin(BaseAdmin):
    list_display = ('store', 'tax_rate', 'tax_inclusive', 'point_rate', 'payment_timeout_seconds')
    list_filter = ('tax_inclusive',)
    search_fields = ('store__name',)


# ===== 決済・金融関連 =====
@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(BaseAdmin):
    list_display = ('transaction_id', 'customer', 'store', 'total_amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('transaction_id', 'customer__username', 'store__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('transaction_id', 'created_at', 'completed_at')
    
    fieldsets = (
        ('取引基本情報', {
            'fields': ('transaction_id', 'customer', 'store', 'terminal_id')
        }),
        ('決済情報', {
            'fields': ('payment_method', 'subtotal', 'tax_amount', 'total_amount', 'status')
        }),
        ('ポイント情報', {
            'fields': ('points_earned', 'points_used', 'points_balance_before', 'points_balance_after')
        }),
        ('外部連携', {
            'fields': ('fincode_payment_id', 'fincode_order_id', 'external_payment_data'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentTransactionItem)
class PaymentTransactionItemAdmin(BaseAdmin):
    list_display = ('transaction', 'item_name', 'unit_price', 'quantity', 'subtotal')
    list_filter = ('transaction__created_at',)
    search_fields = ('item_name', 'item_code', 'transaction__transaction_id')


@admin.register(Receipt)
class ReceiptAdmin(BaseAdmin):
    list_display = ('receipt_number', 'transaction', 'status', 'email_sent_at', 'generated_at')
    list_filter = ('status', 'generated_at')
    search_fields = ('receipt_number', 'transaction__transaction_id')


# ===== ポイントシステム =====
@admin.register(PointTransaction)
class PointTransactionAdmin(BaseAdmin):
    list_display = ('id', 'user', 'store', 'points', 'transaction_type', 'balance_after', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username', 'store__name', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'balance_before', 'balance_after')


@admin.register(PointTransfer)
class PointTransferAdmin(BaseAdmin):
    list_display = ('sender', 'recipient', 'points', 'status', 'transfer_fee', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__username', 'recipient__username')
    readonly_fields = ('created_at', 'processed_at')


@admin.register(UserPoint)
class UserPointAdmin(BaseAdmin):
    list_display = ('user', 'points', 'expiry_date', 'is_expired', 'created_at')
    list_filter = ('is_expired', 'expiry_date', 'created_at')
    search_fields = ('user__username',)


# ===== ギフト・商品関連 =====
@admin.register(Gift)
class GiftAdmin(BaseAdmin):
    list_display = ('name', 'category', 'points_required', 'stock_quantity', 'is_available', 'created_at')
    list_filter = ('category', 'is_available', 'created_at')
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'category', 'description', 'image_url')
        }),
        ('ポイント設定', {
            'fields': ('points_required', 'stock_quantity', 'is_available')
        }),
    )


@admin.register(GiftCategory)
class GiftCategoryAdmin(BaseAdmin):
    list_display = ('name', 'gift_count', 'is_active')
    search_fields = ('name', 'description')
    
    def gift_count(self, obj):
        return obj.gift_set.count()
    gift_count.short_description = 'ギフト数'


@admin.register(DigitalGiftBrand)
class DigitalGiftBrandAdmin(BaseAdmin):
    list_display = ('name', 'api_endpoint', 'is_active', 'purchase_count')
    list_filter = ('is_active',)
    search_fields = ('name',)
    
    def purchase_count(self, obj):
        return obj.digitalgiftpurchase_set.count()
    purchase_count.short_description = '購入件数'


# ===== 通知・コミュニケーション =====
@admin.register(Notification)
class NotificationAdmin(BaseAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'is_sent', 'created_at')
    list_filter = ('notification_type', 'is_read', 'is_sent', 'created_at')
    search_fields = ('user__username', 'title')
    date_hierarchy = 'created_at'


@admin.register(EmailTemplate)
class EmailTemplateAdmin(BaseAdmin):
    list_display = ('name', 'subject', 'template_type', 'is_active')
    list_filter = ('template_type', 'is_active')
    search_fields = ('name', 'subject')


@admin.register(EmailLog)
class EmailLogAdmin(BaseAdmin):
    list_display = ('recipient_email', 'subject', 'status', 'sent_at')
    list_filter = ('status', 'sent_at')
    search_fields = ('recipient_email', 'subject')
    readonly_fields = ('sent_at',)


# ===== セキュリティ・監査 =====
@admin.register(SecurityLog)
class SecurityLogAdmin(BaseAdmin):
    list_display = ('user', 'event_type', 'ip_address', 'user_agent_short', 'risk_score', 'timestamp')
    list_filter = ('event_type', 'risk_score', 'timestamp')
    search_fields = ('user__username', 'ip_address', 'event_details')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    
    def user_agent_short(self, obj):
        return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
    user_agent_short.short_description = 'User Agent'


@admin.register(AuditLog)
class AuditLogAdmin(BaseAdmin):
    list_display = ('user', 'action_type', 'object_type', 'object_id', 'timestamp')
    list_filter = ('action_type', 'object_type', 'timestamp')
    search_fields = ('user__username', 'object_repr', 'changes')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)


# ===== EC・外部連携 =====
@admin.register(ECPointRequest)
class ECPointRequestAdmin(BaseAdmin):
    list_display = ('order_id', 'user', 'store', 'points_to_award', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_id', 'user__username', 'store__name')
    readonly_fields = ('created_at', 'processed_at', 'request_hash')


@admin.register(MeltyRankConfiguration)
class MeltyRankConfigurationAdmin(BaseAdmin):
    list_display = ('melty_membership_type', 'biid_initial_rank', 'welcome_bonus_points', 'is_active')
    list_filter = ('is_active', 'biid_initial_rank', 'melty_membership_type')
    list_editable = ('welcome_bonus_points', 'is_active')


# ===== システム・その他 =====
@admin.register(Area)
class AreaAdmin(BaseAdmin):
    list_display = ('name', 'store_count')
    search_fields = ('name',)
    
    def store_count(self, obj):
        return Store.objects.filter(area=obj.name).count()
    store_count.short_description = '店舗数'


@admin.register(Brand)
class BrandAdmin(BaseAdmin):
    list_display = ('name', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name',)


# ===== 管理画面カスタマイズ =====
admin.site.site_header = 'BIID Point App 運営管理画面'
admin.site.site_title = 'BIID Point App Admin'
admin.site.index_title = 'システム管理'

# ===== 残りのモデル登録 =====

@admin.register(GiftExchange)
class GiftExchangeAdmin(BaseAdmin):
    list_display = ('user', 'gift', 'points_used', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'gift__name')

@admin.register(GiftPurchase) 
class GiftPurchaseAdmin(BaseAdmin):
    list_display = ('user', 'gift', 'purchase_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')

@admin.register(DigitalGiftPurchase)
class DigitalGiftPurchaseAdmin(BaseAdmin):
    list_display = ('user', 'brand', 'amount', 'status', 'gift_code', 'expire_at')
    list_filter = ('status', 'brand', 'created_at')
    search_fields = ('user__username', 'gift_code')

@admin.register(PaymentLog)
class PaymentLogAdmin(BaseAdmin):
    list_display = ('transaction', 'level', 'message', 'timestamp')
    list_filter = ('level', 'timestamp')
    search_fields = ('transaction__transaction_id', 'message')

@admin.register(DepositTransaction)
class DepositTransactionAdmin(BaseAdmin):
    list_display = ('store', 'transaction_type', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')

@admin.register(PointPurchaseTransaction)
class PointPurchaseTransactionAdmin(BaseAdmin):
    list_display = ('transaction_id', 'target_user', 'points_purchased', 'payment_amount', 'payment_status')
    list_filter = ('payment_status', 'created_at')
    search_fields = ('transaction_id', 'target_user__username')

@admin.register(MonthlyBilling)
class MonthlyBillingAdmin(BaseAdmin):
    list_display = ('store', 'billing_year', 'billing_month', 'total_amount', 'status', 'due_date')
    list_filter = ('status', 'billing_year', 'billing_month')

@admin.register(RefundRequest)
class RefundRequestAdmin(BaseAdmin):
    list_display = ('user', 'refund_amount', 'refund_type', 'status', 'requested_at')
    list_filter = ('refund_type', 'status', 'requested_at')
    search_fields = ('user__username', 'reason')

@admin.register(StoreWebhookKey) 
class StoreWebhookKeyAdmin(BaseAdmin):
    list_display = ('store', 'webhook_url', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')

@admin.register(PromotionMail)
class PromotionMailAdmin(BaseAdmin):
    list_display = ('title', 'store', 'recipients_count', 'sent_count', 'status', 'scheduled_at')
    list_filter = ('status', 'target_area', 'created_at')

@admin.register(PointAwardLog)
class PointAwardLogAdmin(BaseAdmin):
    list_display = ('ec_request', 'points_awarded', 'awarded_at', 'awarded_by')
    list_filter = ('awarded_at',)

@admin.register(APIRateLimit)
class APIRateLimitAdmin(BaseAdmin):
    list_display = ('ip_address', 'endpoint', 'request_count', 'window_start', 'is_blocked')
    list_filter = ('is_blocked', 'endpoint', 'window_start')
    search_fields = ('ip_address', 'endpoint')

@admin.register(DuplicateDetection)
class DuplicateDetectionAdmin(BaseAdmin):
    list_display = ('detection_type', 'identifier_hash', 'is_duplicate', 'created_at')
    list_filter = ('detection_type', 'is_duplicate', 'created_at')

@admin.register(BlogTheme)
class BlogThemeAdmin(BaseAdmin):
    list_display = ('name', 'is_active', 'is_premium', 'price', 'created_at')
    list_filter = ('is_active', 'is_premium')
    search_fields = ('name', 'description')

@admin.register(UserBlogTheme)
class UserBlogThemeAdmin(BaseAdmin):
    list_display = ('user', 'theme', 'purchased_at')
    search_fields = ('user__username', 'theme__name')

@admin.register(PurchaseID)
class PurchaseIDAdmin(BaseAdmin):
    list_display = ('purchase_id', 'gift_type', 'is_used', 'created_at')
    list_filter = ('gift_type', 'is_used', 'created_at')
    search_fields = ('purchase_id',)

@admin.register(DigitalGiftUsageLog)
class DigitalGiftUsageLogAdmin(BaseAdmin):
    list_display = ('purchase', 'used_at', 'usage_details')
    list_filter = ('used_at',)

@admin.register(DigitalGiftPurchaseID)
class DigitalGiftPurchaseIDAdmin(BaseAdmin):
    list_display = ('purchase_id', 'digital_gift_brand', 'is_used', 'created_at')
    list_filter = ('is_used', 'created_at')

@admin.register(DepositUsageLog)
class DepositUsageLogAdmin(BaseAdmin):
    list_display = ('deposit_transaction', 'used_amount', 'used_at', 'description')
    list_filter = ('used_at',)

@admin.register(DepositAutoChargeRule)
class DepositAutoChargeRuleAdmin(BaseAdmin):
    list_display = ('store', 'trigger_amount', 'charge_amount', 'is_active')
    list_filter = ('is_active',)

# ===== 管理画面カスタマイズ =====
admin.site.site_header = 'BIID Point App 運営管理画面'
admin.site.site_title = 'BIID Point App Admin' 
admin.site.index_title = 'システム管理'

# 本番用ダッシュボードへのリンクを追加
from django.urls import reverse
from django.utils.html import format_html

def production_dashboard_link():
    """本番用ダッシュボードへのリンク"""
    return format_html(
        '<div style="background: #417690; padding: 15px; border-radius: 5px; margin: 20px 0;">'
        '<h3 style="color: white; margin: 0 0 10px 0;">'
        '<i class="fas fa-tachometer-alt"></i> 本番運営ダッシュボード</h3>'
        '<p style="color: #e1f0ff; margin: 0 0 10px 0;">統合システム管理・リアルタイム統計・セキュリティ監視</p>'
        '<a href="/production-admin/" style="background: #28a745; color: white; padding: 10px 20px; '
        'text-decoration: none; border-radius: 3px; display: inline-block; font-weight: bold;">'
        '🚀 本番管理画面を開く</a>'
        '</div>'
    )

# Django Adminのindex.htmlテンプレートをカスタマイズ
admin.site.index_template = 'admin/custom_index.html'