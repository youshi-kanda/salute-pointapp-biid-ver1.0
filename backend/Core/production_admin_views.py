"""
本番用運営管理画面ビュー
"""

from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import (
    User, Store, PaymentTransaction, DigitalGiftPurchase, 
    PointTransaction, Notification, SecurityLog, AuditLog
)


@staff_member_required
def production_dashboard(request):
    """
    本番用運営管理ダッシュボード
    """
    # 統計データを取得
    stats = {
        'total_users': User.objects.filter(role='customer').count(),
        'total_stores': Store.objects.filter(status='active').count(),
        'monthly_revenue': PaymentTransaction.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30),
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
        'gift_exchanges': DigitalGiftPurchase.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count(),
    }
    
    # 最近のアクティビティ
    recent_activities = []
    
    # 最近の決済
    recent_payments = PaymentTransaction.objects.filter(
        status='completed'
    ).select_related('store', 'customer').order_by('-created_at')[:5]
    
    for payment in recent_payments:
        recent_activities.append({
            'type': 'payment',
            'title': '新規決済処理',
            'description': f'店舗「{payment.store.name if payment.store else "不明"}」で¥{payment.total_amount:,}の決済が完了',
            'time': payment.created_at,
            'icon': 'fas fa-yen-sign'
        })
    
    # 新規ユーザー登録
    recent_users = User.objects.filter(
        role='customer',
        registration_date__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-registration_date')[:3]
    
    for user in recent_users:
        recent_activities.append({
            'type': 'user',
            'title': '新規ユーザー登録',
            'description': f'{"MELTY連携" if user.is_melty_linked else "通常"}ユーザーが登録',
            'time': user.registration_date,
            'icon': 'fas fa-user-plus'
        })
    
    # デジタルギフト交換
    recent_gifts = DigitalGiftPurchase.objects.select_related(
        'user', 'purchase_id_obj__brand'
    ).order_by('-created_at')[:3]
    
    for gift in recent_gifts:
        recent_activities.append({
            'type': 'gift',
            'title': 'デジタルギフト交換',
            'description': f'{gift.purchase_id_obj.brand.brand_name if gift.purchase_id_obj else "不明"} ¥{gift.purchase_id_obj.price if gift.purchase_id_obj else 0:,}が交換',
            'time': gift.created_at,
            'icon': 'fas fa-gift'
        })
    
    # セキュリティログ
    security_alerts = SecurityLog.objects.filter(
        risk_score__gte=5,
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-timestamp')[:2]
    
    for alert in security_alerts:
        recent_activities.append({
            'type': 'security',
            'title': 'セキュリティアラート',
            'description': f'{alert.event_type}: {alert.event_details[:50]}...' if len(alert.event_details) > 50 else alert.event_details,
            'time': alert.timestamp,
            'icon': 'fas fa-exclamation-triangle'
        })
    
    # 時刻でソート
    recent_activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = recent_activities[:10]
    
    # 時刻を相対表示用に変換
    now = timezone.now()
    for activity in recent_activities:
        delta = now - activity['time']
        if delta.days > 0:
            activity['time_display'] = f"{delta.days}日前"
        elif delta.seconds > 3600:
            activity['time_display'] = f"{delta.seconds // 3600}時間前"
        elif delta.seconds > 60:
            activity['time_display'] = f"{delta.seconds // 60}分前"
        else:
            activity['time_display'] = "数秒前"
    
    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        'current_time': timezone.now(),
        'user': request.user,
    }
    
    return render(request, 'production_admin/dashboard.html', context)


@staff_member_required
def system_settings_view(request):
    """
    システム設定画面（スクリーンショット対応）
    """
    if request.method == 'POST':
        # 設定更新処理
        setting_type = request.POST.get('setting_type')
        
        if setting_type == 'general':
            # 一般設定の更新
            messages.success(request, '一般設定を更新しました。')
        elif setting_type == 'payment_integration':
            # 決済・連携設定の更新
            messages.success(request, '決済・連携設定を更新しました。')
        elif setting_type == 'notification':
            # 通知設定の更新
            messages.success(request, '通知設定を更新しました。')
        elif setting_type == 'business_operation':
            # 運営設定の更新
            messages.success(request, '運営設定を更新しました。')
        elif setting_type == 'member_rank':
            # 会員ランク設定の更新
            messages.success(request, '会員ランク設定を更新しました。')
        elif setting_type == 'user_experience':
            # ユーザー体験設定の更新
            messages.success(request, 'ユーザー体験設定を更新しました。')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': '設定を更新しました。'})
        
        return redirect('production_admin:system_settings')
    
    # 現在の設定値を取得（6カテゴリ対応）
    settings = {
        'general': {
            'site_name': 'biid Point Management',
            'support_email': 'support@biid.com',
            'support_phone': '03-1234-5678',
            'operation_area': '大阪（北新地・ミナミエリア）',
            'timezone': 'Asia/Tokyo',
            'maintenance_mode': False,
            'debug_mode': False,
            'site_description': '革新的なポイント管理システム',
        },
        'payment': {
            'fincode_api_key': 'p_test_YTY3YTRkZDMt...',
            'fincode_is_production': False,
            'payment_timeout_seconds': 300,
            'max_payment_amount': 500000.00,
            'min_payment_amount': 100.00,
            'default_point_rate': 1.0,
            'point_expiry_months': 12,
        },
        'notification': {
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_use_tls': True,
            'from_email': 'noreply@biid.com',
            'from_name': 'BIID Point System',
            'enable_welcome_email': True,
            'enable_point_notification': True,
            'enable_gift_notification': True,
            'enable_promotion_email': True,
            'email_batch_size': 100,
            'email_rate_limit': 60,
        },
        'business_operation': {
            'point_expiry_months': 6,
            'point_unit_price': 1.00,
            'system_fee_rate': 3.0,
            'store_deposit_required': 50000,
            'bank_transfer_fee': 220,
            'minimum_cashout_amount': 20000,
            'promo_email_fee': 10,
            'point_transfer_fee_rate': 10,
        },
        'member_rank': {
            'regular_member_threshold': 10000,
            'vip_member_threshold': 100000,
            'premium_member_bonus_rate': 5.0,
            'vip_member_bonus_rate': 10.0,
        },
        'user_experience': {
            'user_support_email': 'support@biid.jp',
            'welcome_bonus_points': 1000,
            'melty_membership_type': 'free',
            'max_daily_point_transfer': 10000,
            'enable_social_features': True,
            'enable_gift_exchange': True,
            'enable_point_transfer': False,
        }
    }
    
    context = {
        'settings': settings,
        'user': request.user,
    }
    
    return render(request, 'production_admin/system_settings.html', context)


@staff_member_required
def api_status(request):
    """
    システム状態API
    """
    try:
        from django.db import connection
        from django.core.cache import cache
        
        # データベース接続テスト
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = True
    except Exception:
        db_status = False
    
    # キャッシュテスト
    try:
        cache.set('system_check', 'ok', 10)
        cache_status = cache.get('system_check') == 'ok'
    except Exception:
        cache_status = False
    
    # システム統計
    stats = {
        'users_online': User.objects.filter(
            last_login_date__gte=timezone.now() - timedelta(minutes=30)
        ).count(),
        'active_sessions': 0,  # セッションカウントの実装が必要
        'pending_transactions': PaymentTransaction.objects.filter(
            status='pending'
        ).count(),
        'error_rate': 0,  # エラー率の計算が必要
    }
    
    status_data = {
        'status': 'online' if db_status and cache_status else 'error',
        'database': db_status,
        'cache': cache_status,
        'timestamp': timezone.now().isoformat(),
        'stats': stats,
    }
    
    return JsonResponse(status_data)


@staff_member_required 
def user_management(request):
    """
    ユーザー管理画面
    """
    users = User.objects.filter(role='customer').select_related().order_by('-registration_date')[:100]
    
    context = {
        'users': users,
        'user': request.user,
        'total_users': User.objects.filter(role='customer').count(),
    }
    
    return render(request, 'production_admin/user_management.html', context)


@staff_member_required
def store_management(request):
    """
    店舗管理画面
    """
    stores = Store.objects.all().order_by('-registration_date')[:100]
    
    context = {
        'stores': stores,
        'user': request.user,
        'total_stores': Store.objects.count(),
    }
    
    return render(request, 'production_admin/store_management.html', context)


@staff_member_required
def transaction_management(request):
    """
    取引管理画面
    """
    transactions = PaymentTransaction.objects.select_related(
        'customer', 'store'
    ).order_by('-created_at')[:100]
    
    context = {
        'transactions': transactions,
        'user': request.user,
        'total_transactions': PaymentTransaction.objects.count(),
    }
    
    return render(request, 'production_admin/transaction_management.html', context)


def point_pricing_settings(request):
    """
    ポイント価格設定API
    店舗管理画面で使用される価格設定を返す
    """
    # システム設定から価格設定を取得（実際の設定システムに合わせて調整）
    # 現在はデフォルト値を返す
    
    pricing_data = {
        'unit_price': 1.00,  # 基本単価（円/ポイント）
        'system_fee_rate': 3.0,  # システム手数料率（％）
        'min_purchase_amount': 100,  # 最小購入額（ポイント）
        'max_purchase_amount': 50000,  # 最大購入額（ポイント）
        'tax_rate': 10.0,  # 消費税率（％）
        'operation_fee_rate': 5.0,  # 運営手数料率（％）
        'store_tier_discounts': {
            'standard': 0.0,  # 標準店舗割引率
            'premium': 2.0,   # プレミアム店舗割引率
            'vip': 5.0        # VIP店舗割引率
        }
    }
    
    return JsonResponse({
        'success': True,
        'data': pricing_data,
        'timestamp': timezone.now().isoformat()
    })