"""
BIID Point App 本番環境用 Django Admin 設定（修正版）
実際のモデルフィールドに合わせて調整
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    # 基本モデルのみ確実に存在するものを登録
    User, Store, PointTransaction, AccountRank, 
    PaymentTransaction, Receipt, Notification,
    Gift, GiftCategory, SecurityLog, AuditLog,
    MeltyRankConfiguration
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
    list_filter = ('status', 'rank', 'registration_source', 'is_melty_linked', 'registration_date')
    search_fields = ('username', 'email', 'member_id')
    date_hierarchy = 'registration_date'
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('BIID Point System', {
            'fields': ('member_id', 'rank', 'status', 'location', 'avatar')
        }),
        ('MELTY Integration', {
            'fields': ('is_melty_linked', 'melty_user_id', 'melty_email', 'melty_connected_at', 'registration_source'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = BaseUserAdmin.readonly_fields + ('melty_connected_at', 'registration_date')
    
    actions = ['reset_melty_link', 'upgrade_to_silver', 'upgrade_to_gold', 'suspend_users', 'activate_users']
    
    def point_balance_display(self, obj):
        return f"{obj.point_balance:,}pt" if hasattr(obj, 'point_balance') else "0pt"
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


# ===== 店舗関連 =====
@admin.register(Store)
class StoreAdmin(BaseAdmin):
    list_display = ('name', 'owner_name', 'category', 'status', 'registration_date')
    list_filter = ('status', 'category', 'registration_date')
    search_fields = ('name', 'owner_name', 'email')
    date_hierarchy = 'registration_date'
    readonly_fields = ('registration_date',)


# ===== 決済・金融関連 =====
@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(BaseAdmin):
    list_display = ('transaction_id', 'customer', 'store', 'total_amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('transaction_id', 'customer__username', 'store__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('transaction_id', 'created_at', 'completed_at')


@admin.register(Receipt)
class ReceiptAdmin(BaseAdmin):
    list_display = ('receipt_number', 'transaction', 'status', 'generated_at')
    list_filter = ('status', 'generated_at')
    search_fields = ('receipt_number', 'transaction__transaction_id')
    readonly_fields = ('generated_at',)


# ===== ポイントシステム =====
@admin.register(PointTransaction)
class PointTransactionAdmin(BaseAdmin):
    list_display = ('id', 'user', 'store', 'points', 'transaction_type', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username', 'store__name', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)


# ===== ギフト・商品関連 =====
@admin.register(Gift)
class GiftAdmin(BaseAdmin):
    list_display = ('name', 'category', 'points_required', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'category', 'description', 'image_url')
        }),
        ('ポイント設定', {
            'fields': ('points_required',)
        }),
    )


@admin.register(GiftCategory)
class GiftCategoryAdmin(BaseAdmin):
    list_display = ('name', 'gift_count')
    search_fields = ('name', 'description')
    
    def gift_count(self, obj):
        return obj.gift_set.count()
    gift_count.short_description = 'ギフト数'


# ===== 通知・コミュニケーション =====
@admin.register(Notification)
class NotificationAdmin(BaseAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'is_sent', 'created_at')
    list_filter = ('notification_type', 'is_read', 'is_sent', 'created_at')
    search_fields = ('user__username', 'title')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)


# ===== セキュリティ・監査 =====
@admin.register(SecurityLog)
class SecurityLogAdmin(BaseAdmin):
    list_display = ('user', 'event_type', 'ip_address', 'user_agent_short', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__username', 'ip_address')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    
    def user_agent_short(self, obj):
        return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
    user_agent_short.short_description = 'User Agent'


@admin.register(AuditLog)
class AuditLogAdmin(BaseAdmin):
    list_display = ('user', 'action_type', 'object_type', 'object_id', 'timestamp')
    list_filter = ('action_type', 'object_type', 'timestamp')
    search_fields = ('user__username', 'object_repr')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)


# ===== EC・外部連携 =====
@admin.register(MeltyRankConfiguration)
class MeltyRankConfigurationAdmin(BaseAdmin):
    list_display = ('melty_membership_type', 'biid_initial_rank', 'welcome_bonus_points', 'is_active')
    list_filter = ('is_active', 'biid_initial_rank', 'melty_membership_type')
    list_editable = ('welcome_bonus_points', 'is_active')
    
    fieldsets = (
        ('MELTY会員種別', {
            'fields': ('melty_membership_type', 'biid_initial_rank')
        }),
        ('ウェルカムボーナス設定', {
            'fields': ('welcome_bonus_points', 'points_expiry_months')
        }),
        ('会員ID設定', {
            'fields': ('member_id_prefix',)
        }),
        ('状態・説明', {
            'fields': ('is_active', 'description')
        }),
    )


# ===== 管理画面カスタマイズ =====
admin.site.site_header = 'BIID Point App 運営管理画面'
admin.site.site_title = 'BIID Point App Admin'
admin.site.index_title = 'システム管理'

# 本番環境用の管理画面設定
if hasattr(admin.site, 'enable_nav_sidebar'):
    admin.site.enable_nav_sidebar = False  # サイドバー無効化（パフォーマンス向上）