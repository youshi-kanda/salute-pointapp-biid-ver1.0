from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Store, PointTransaction, AccountRank, 
    MeltyRankConfiguration
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'member_id', 'point_balance', 'rank', 'melty_linked_status', 'status', 'registration_date')
    list_filter = ('status', 'rank', 'registration_source', 'is_melty_linked', 'registration_date', 'last_login_date')
    search_fields = ('username', 'email', 'member_id')
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Point System Info', {
            'fields': ('member_id', 'rank', 'status', 'location', 'avatar')
        }),
        ('MELTY Integration', {
            'fields': ('is_melty_linked', 'melty_user_id', 'melty_email', 'melty_connected_at', 'registration_source'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = BaseUserAdmin.readonly_fields + ('melty_connected_at',)
    
    actions = ['reset_melty_link', 'upgrade_to_silver', 'upgrade_to_gold']
    
    def reset_melty_link(self, request, queryset):
        """MELTY連携をリセット"""
        count = 0
        for user in queryset:
            if user.is_melty_linked:
                user.is_melty_linked = False
                user.melty_user_id = None
                user.melty_email = None
                user.melty_connected_at = None
                user.melty_profile_data = {}
                user.save()
                count += 1
        self.message_user(request, f'{count}件のMELTY連携をリセットしました。')
    reset_melty_link.short_description = 'MELTY連携をリセット'
    
    def upgrade_to_silver(self, request, queryset):
        """シルバーランクにアップグレード"""
        count = 0
        for user in queryset.filter(rank='bronze'):
            user.rank = 'silver'
            user.save()
            count += 1
        self.message_user(request, f'{count}件のユーザーをシルバーランクにアップグレードしました。')
    upgrade_to_silver.short_description = 'シルバーランクにアップグレード'
    
    def upgrade_to_gold(self, request, queryset):
        """ゴールドランクにアップグレード"""
        count = 0
        for user in queryset.filter(rank__in=['bronze', 'silver']):
            user.rank = 'gold'
            user.save()
            count += 1
        self.message_user(request, f'{count}件のユーザーをゴールドランクにアップグレードしました。')
    upgrade_to_gold.short_description = 'ゴールドランクにアップグレード'
    
    def point_balance(self, obj):
        """ポイント残高を表示"""
        return f"{obj.point_balance}pt"
    point_balance.short_description = 'ポイント残高'
    
    def melty_linked_status(self, obj):
        """MELTY連携状態を表示"""
        if obj.is_melty_linked:
            config = obj.get_melty_configuration()
            membership = config.get_melty_membership_type_display() if config else 'N/A'
            return f"連携済み ({membership})"
        return "連携なし"
    melty_linked_status.short_description = 'MELTY連携'


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner_name', 'category', 'status', 'point_rate', 'registration_date')
    list_filter = ('status', 'category', 'price_range', 'biid_partner')
    search_fields = ('name', 'owner_name', 'email')
    readonly_fields = ('registration_date',)


@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'store', 'points', 'transaction_type', 'balance_after', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username', 'store__name', 'description')
    readonly_fields = ('created_at', 'balance_before', 'balance_after')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'store', 'processed_by')


@admin.register(AccountRank)
class AccountRankAdmin(admin.ModelAdmin):
    """アカウントランク管理"""
    list_display = ('rank', 'required_points', 'required_transactions', 'point_multiplier')
    list_filter = ('rank',)
    ordering = ['required_points']
    
    fieldsets = (
        ('基本設定', {
            'fields': ('rank', 'required_points', 'required_transactions')
        }),
        ('ランク特典', {
            'fields': ('point_multiplier', 'privileges')
        }),
    )


@admin.register(MeltyRankConfiguration)
class MeltyRankConfigurationAdmin(admin.ModelAdmin):
    """MELTY会員ランク設定管理"""
    list_display = (
        'melty_membership_type', 'biid_initial_rank', 'welcome_bonus_points', 
        'points_expiry_months', 'member_id_prefix', 'is_active'
    )
    list_filter = ('is_active', 'biid_initial_rank', 'melty_membership_type')
    list_editable = ('welcome_bonus_points', 'points_expiry_months', 'is_active')
    ordering = ['melty_membership_type']
    
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
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # 編集時
            return ['melty_membership_type']  # 会員種別は変更不可
        return []
    
    def has_delete_permission(self, request, obj=None):
        # デフォルト設定は削除不可
        if obj and obj.melty_membership_type in ['free', 'premium']:
            return False
        return True
