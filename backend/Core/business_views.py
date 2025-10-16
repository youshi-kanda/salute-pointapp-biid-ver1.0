from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator  
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
import json
from decimal import Decimal
from datetime import datetime, timedelta

from .models import (
    User, Store, PointTransaction, UserPoint, PointTransfer, 
    Notification, PromotionMail, AccountRank, RefundRequest,
    BlogTheme, UserBlogTheme, Area, EmailTemplate, EmailLog
)
from .serializers import (
    UserPointSerializer, PointTransferSerializer, NotificationSerializer,
    PromotionMailSerializer, RefundRequestSerializer, BlogThemeSerializer,
    AreaSerializer, StoreSerializer, EmailTemplateSerializer, EmailLogSerializer
)
from .email_service import email_service
from .point_service import point_service


# === ポイント有効期限管理 ===

@login_required
@csrf_exempt
@require_http_methods(["GET"])
def user_points_detail(request):
    """ユーザーの詳細ポイント情報を取得"""
    try:
        user_points = UserPoint.objects.filter(
            user=request.user, 
            is_expired=False
        ).order_by('expiry_date')
        
        # 期限切れチェック
        for point in user_points:
            point.is_valid()
        
        # 有効なポイントのみ再取得
        valid_points = user_points.filter(is_expired=False)
        total_points = sum(point.points for point in valid_points)
        
        # 期限別の集計
        expiring_soon = valid_points.filter(
            expiry_date__lte=timezone.now() + timedelta(days=30)
        )
        
        return JsonResponse({
            'success': True,
            'total_points': total_points,
            'points_detail': UserPointSerializer(valid_points, many=True).data,
            'expiring_soon': UserPointSerializer(expiring_soon, many=True).data,
            'expiring_soon_total': sum(point.points for point in expiring_soon)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === ポイント転送機能 ===

@login_required
@csrf_exempt  
@require_http_methods(["POST"])
def transfer_points(request):
    """ポイント転送"""
    try:
        data = json.loads(request.body)
        recipient_id = data.get('recipient_id')
        points = int(data.get('points', 0))
        message = data.get('message', '')
        
        if points <= 0:
            return JsonResponse({
                'success': False,
                'error': 'ポイント数は1以上である必要があります'
            }, status=400)
        
        # 受取人の存在確認
        try:
            recipient = User.objects.get(id=recipient_id)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '受取人が存在しません'
            }, status=404)
        
        # 自分自身への転送チェック
        if recipient == request.user:
            return JsonResponse({
                'success': False,
                'error': '自分自身にはポイントを転送できません'
            }, status=400)
        
        # 統一ポイントサービスを使用して転送処理
        try:
            transfer = point_service.create_point_transfer(
                sender=request.user,
                recipient=recipient,
                points=points,
                message=message
            )
            
            # 転送実行
            point_service.execute_point_transfer(transfer.id)
        
            return JsonResponse({
                'success': True,
                'transfer_id': transfer.id,
                'points_transferred': points,
                'transfer_fee': transfer.transfer_fee,
                'remaining_balance': request.user.point_balance
            })
            
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'ポイント転送に失敗しました'
            }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def transfer_history(request):
    """ポイント転送履歴"""
    try:
        # 送信・受信両方の履歴を取得
        sent_transfers = PointTransfer.objects.filter(sender=request.user)
        received_transfers = PointTransfer.objects.filter(recipient=request.user)
        
        # ページネーション
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        all_transfers = (sent_transfers.union(received_transfers)).order_by('-created_at')
        paginator = Paginator(all_transfers, per_page)
        transfers = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'transfers': PointTransferSerializer(transfers, many=True).data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === 通知機能 ===

@login_required
@csrf_exempt
@require_http_methods(["GET"])
def notifications(request):
    """ユーザー通知一覧"""
    try:
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        
        # 未読のみフィルター
        if request.GET.get('unread_only') == 'true':
            notifications = notifications.filter(is_read=False)
        
        # ページネーション
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        paginator = Paginator(notifications, per_page)
        notifications_page = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'notifications': NotificationSerializer(notifications_page, many=True).data,
            'unread_count': notifications.filter(is_read=False).count(),
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """通知を既読にする"""
    try:
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            user=request.user
        )
        
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        
        return JsonResponse({
            'success': True,
            'message': '通知を既読にしました'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === ポイント払戻し申請・管理機能 ===

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_refund_request(request):
    """ポイント払戻し申請"""
    try:
        data = json.loads(request.body)
        points_to_refund = int(data.get('points_to_refund', 0))
        refund_type = data.get('refund_type')
        reason = data.get('reason', '')
        
        # バリデーション
        if points_to_refund <= 0:
            return JsonResponse({
                'success': False,
                'error': 'ポイント数は1以上である必要があります'
            }, status=400)
        
        if request.user.points < points_to_refund:
            return JsonResponse({
                'success': False,
                'error': 'ポイント残高が不足しています'
            }, status=400)
        
        # 処理手数料計算（10%）
        processing_fee = Decimal(points_to_refund) * Decimal('0.10')
        
        # 払戻し申請作成
        refund_request = RefundRequest.objects.create(
            user=request.user,
            points_to_refund=points_to_refund,
            refund_type=refund_type,
            reason=reason,
            processing_fee=processing_fee
        )
        
        # 払戻し金額計算
        refund_request.calculate_refund_amount()
        refund_request.save()
        
        # 銀行情報が必要な場合
        if refund_type == 'bank_transfer':
            bank_info = data.get('bank_info', {})
            refund_request.bank_name = bank_info.get('bank_name', '')
            refund_request.branch_name = bank_info.get('branch_name', '')
            refund_request.account_type = bank_info.get('account_type', '')
            refund_request.account_number = bank_info.get('account_number', '')
            refund_request.account_holder = bank_info.get('account_holder', '')
            refund_request.save()
        
        # 通知作成
        Notification.objects.create(
            user=request.user,
            notification_type='system',
            title='払戻し申請を受け付けました',
            message=f'{points_to_refund}ポイントの払戻し申請を受け付けました。審査結果をお待ちください。'
        )
        
        return JsonResponse({
            'success': True,
            'refund_request_id': refund_request.id,
            'processing_fee': float(processing_fee),
            'estimated_refund_amount': float(refund_request.refund_amount)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def refund_requests(request):
    """払戻し申請履歴"""
    try:
        requests_qs = RefundRequest.objects.filter(user=request.user).order_by('-requested_at')
        
        # ページネーション
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        paginator = Paginator(requests_qs, per_page)
        requests_page = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'requests': RefundRequestSerializer(requests_page, many=True).data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === 管理者用払戻し管理 ===

@staff_member_required
@csrf_exempt
@require_http_methods(["GET"])
def admin_refund_requests(request):
    """管理者用: 払戻し申請一覧"""
    try:
        status_filter = request.GET.get('status')
        
        requests_qs = RefundRequest.objects.all().order_by('-requested_at')
        
        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter)
        
        # ページネーション
        page = int(request.GET.get('page', 1))  
        per_page = int(request.GET.get('per_page', 20))
        
        paginator = Paginator(requests_qs, per_page)
        requests_page = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'requests': RefundRequestSerializer(requests_page, many=True).data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["POST"])
def process_refund_request(request, request_id):
    """管理者用: 払戻し申請処理"""
    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'approve' or 'reject'
        admin_notes = data.get('admin_notes', '')
        
        refund_request = get_object_or_404(RefundRequest, id=request_id)
        
        if refund_request.status != 'pending':
            return JsonResponse({
                'success': False,
                'error': '既に処理済みの申請です'
            }, status=400)
        
        with transaction.atomic():
            if action == 'approve':
                refund_request.status = 'approved'
                refund_request.processed_by = request.user
                refund_request.processed_at = timezone.now()
                refund_request.admin_notes = admin_notes
                refund_request.save()
                
                # 通知作成
                Notification.objects.create(
                    user=refund_request.user,
                    notification_type='system',
                    title='払戻し申請が承認されました',
                    message=f'{refund_request.points_to_refund}ポイントの払戻し申請が承認されました。処理を開始いたします。'
                )
                
            elif action == 'reject':
                refund_request.status = 'rejected'
                refund_request.processed_by = request.user
                refund_request.processed_at = timezone.now()
                refund_request.admin_notes = admin_notes
                refund_request.save()
                
                # 通知作成
                Notification.objects.create(
                    user=refund_request.user,
                    notification_type='system',
                    title='払戻し申請が却下されました',
                    message=f'{refund_request.points_to_refund}ポイントの払戻し申請が却下されました。理由: {admin_notes}'
                )
                
            else:
                return JsonResponse({
                    'success': False,
                    'error': '無効なアクションです'
                }, status=400)
        
        return JsonResponse({
            'success': True,
            'message': f'払戻し申請を{action}しました'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === ブログテーマ機能 ===

@csrf_exempt
@require_http_methods(["GET"])
def blog_themes(request):
    """ブログテーマ一覧"""
    try:
        themes = BlogTheme.objects.filter(is_active=True).order_by('-created_at')
        
        return JsonResponse({
            'success': True,
            'themes': BlogThemeSerializer(themes, many=True).data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def purchase_blog_theme(request, theme_id):
    """ブログテーマ購入"""
    try:
        theme = get_object_or_404(BlogTheme, id=theme_id, is_active=True)
        
        # 既に購入済みかチェック
        if UserBlogTheme.objects.filter(user=request.user, theme=theme).exists():
            return JsonResponse({
                'success': False,
                'error': '既に購入済みのテーマです'
            }, status=400)
        
        # ポイント残高チェック（プレミアムテーマの場合）
        if theme.is_premium and theme.price > 0:
            required_points = int(theme.price)
            if request.user.points < required_points:
                return JsonResponse({
                    'success': False,
                    'error': f'ポイントが不足しています（必要: {required_points}ポイント）'
                }, status=400)
            
            # ポイント消費
            request.user.points -= required_points
            request.user.save()
        
        # テーマ購入記録作成
        UserBlogTheme.objects.create(
            user=request.user,
            theme=theme
        )
        
        return JsonResponse({
            'success': True,
            'message': f'テーマ「{theme.name}」を購入しました',
            'remaining_points': request.user.points
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def user_blog_themes(request):
    """ユーザーの購入済みテーマ一覧"""
    try:
        user_themes = UserBlogTheme.objects.filter(user=request.user).select_related('theme')
        
        themes_data = []
        for user_theme in user_themes:
            theme_data = BlogThemeSerializer(user_theme.theme).data
            theme_data['purchased_at'] = user_theme.purchased_at.isoformat()
            themes_data.append(theme_data)
        
        return JsonResponse({
            'success': True,
            'themes': themes_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === エリア展開制限機能 ===

@csrf_exempt
@require_http_methods(["GET"])
def areas_list(request):
    """エリア一覧取得（ユーザー・店舗共通）"""
    try:
        areas = Area.objects.filter(is_active=True).order_by('display_order', 'name')
        
        return JsonResponse({
            'success': True,
            'areas': AreaSerializer(areas, many=True).data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["GET", "POST"])
def admin_areas_manage(request):
    """管理者用: エリア管理（一覧・作成）"""
    if request.method == "GET":
        try:
            areas = Area.objects.all().order_by('display_order', 'name')
            
            return JsonResponse({
                'success': True,
                'areas': AreaSerializer(areas, many=True).data
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            display_order = int(data.get('display_order', 0))
            
            if not name:
                return JsonResponse({
                    'success': False,
                    'error': 'エリア名は必須です'
                }, status=400)
            
            # 重複チェック
            if Area.objects.filter(name=name).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'このエリア名は既に存在します'
                }, status=400)
            
            # エリア作成
            area = Area.objects.create(
                name=name,
                display_order=display_order
            )
            
            return JsonResponse({
                'success': True,
                'area': AreaSerializer(area).data,
                'message': f'エリア「{name}」を作成しました'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def admin_area_detail(request, area_id):
    """管理者用: エリア詳細・更新・削除"""
    try:
        area = get_object_or_404(Area, id=area_id)
    except Area.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'エリアが見つかりません'
        }, status=404)
    
    if request.method == "GET":
        try:
            return JsonResponse({
                'success': True,
                'area': AreaSerializer(area).data
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            display_order = int(data.get('display_order', 0))
            is_active = data.get('is_active', True)
            
            if not name:
                return JsonResponse({
                    'success': False,
                    'error': 'エリア名は必須です'
                }, status=400)
            
            # 重複チェック（自分以外）
            if Area.objects.filter(name=name).exclude(id=area_id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'このエリア名は既に存在します'
                }, status=400)
            
            # エリア更新
            area.name = name
            area.display_order = display_order
            area.is_active = is_active
            area.save()
            
            return JsonResponse({
                'success': True,
                'area': AreaSerializer(area).data,
                'message': f'エリア「{name}」を更新しました'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    elif request.method == "DELETE":
        try:
            # 使用中チェック
            stores_count = area.stores.count()
            promotion_mails_count = area.promotion_mails.count()
            
            if stores_count > 0:
                return JsonResponse({
                    'success': False,
                    'error': f'このエリアは{stores_count}店舗で使用中のため削除できません'
                }, status=400)
            
            if promotion_mails_count > 0:
                return JsonResponse({
                    'success': False,
                    'error': f'このエリアは{promotion_mails_count}件のプロモーションメールで使用中のため削除できません'
                }, status=400)
            
            area_name = area.name
            area.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'エリア「{area_name}」を削除しました'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def stores_by_area(request):
    """エリア別店舗一覧取得"""
    try:
        area_id = request.GET.get('area_id')
        
        # ベースクエリ
        stores = Store.objects.filter(status='active').select_related('area')
        
        # エリアフィルタリング
        if area_id:
            try:
                area_id = int(area_id)
                stores = stores.filter(area_id=area_id)
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'error': '無効なエリアIDです'
                }, status=400)
        
        # その他のフィルタリングオプション
        category = request.GET.get('category')
        if category:
            stores = stores.filter(category=category)
        
        price_range = request.GET.get('price_range')
        if price_range:
            stores = stores.filter(price_range=price_range)
        
        # 並び順
        sort_by = request.GET.get('sort_by', 'rating')
        if sort_by == 'rating':
            stores = stores.order_by('-rating')
        elif sort_by == 'name':
            stores = stores.order_by('name')
        elif sort_by == 'distance':
            # 位置情報がある場合の距離順（簡易実装）
            stores = stores.order_by('latitude', 'longitude')
        
        # ページネーション
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        paginator = Paginator(stores, per_page)
        stores_page = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'stores': StoreSerializer(stores_page, many=True).data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === メール通知管理機能 ===

@staff_member_required
@csrf_exempt
@require_http_methods(["GET"])
def admin_email_templates(request):
    """管理者用: メールテンプレート一覧"""
    try:
        templates = EmailTemplate.objects.all().order_by('name')
        
        return JsonResponse({
            'success': True,
            'templates': EmailTemplateSerializer(templates, many=True).data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["GET", "PUT"])
def admin_email_template_detail(request, template_id):
    """管理者用: メールテンプレート詳細・編集"""
    try:
        template = get_object_or_404(EmailTemplate, id=template_id)
    except EmailTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'テンプレートが見つかりません'
        }, status=404)
    
    if request.method == "GET":
        return JsonResponse({
            'success': True,
            'template': EmailTemplateSerializer(template).data
        })
    
    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            
            # テンプレート更新
            template.subject = data.get('subject', template.subject)
            template.body_html = data.get('body_html', template.body_html)
            template.body_text = data.get('body_text', template.body_text)
            template.description = data.get('description', template.description)
            template.is_active = data.get('is_active', template.is_active)
            template.save()
            
            return JsonResponse({
                'success': True,
                'template': EmailTemplateSerializer(template).data,
                'message': f'テンプレート「{template.name}」を更新しました'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["GET"])
def admin_email_logs(request):
    """管理者用: メール送信ログ一覧"""
    try:
        # フィルタリング
        status = request.GET.get('status')
        template_name = request.GET.get('template')
        recipient_email = request.GET.get('recipient')
        
        logs = EmailLog.objects.all().select_related('notification').order_by('-created_at')
        
        if status:
            logs = logs.filter(status=status)
        if template_name:
            logs = logs.filter(template_used=template_name)
        if recipient_email:
            logs = logs.filter(recipient_email__icontains=recipient_email)
        
        # ページネーション
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        
        paginator = Paginator(logs, per_page)
        logs_page = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'logs': EmailLogSerializer(logs_page, many=True).data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["POST"])
def admin_retry_failed_emails(request):
    """管理者用: 失敗したメールの再送信"""
    try:
        data = json.loads(request.body)
        max_age_hours = int(data.get('max_age_hours', 24))
        
        retry_count = email_service.retry_failed_emails(max_age_hours)
        
        return JsonResponse({
            'success': True,
            'message': f'{retry_count}件のメールを재송信しました',
            'retry_count': retry_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["POST"]) 
def admin_send_test_email(request):
    """管理者用: テストメール送信"""
    try:
        data = json.loads(request.body)
        template_name = data.get('template_name')
        recipient_email = data.get('recipient_email')
        test_context = data.get('context', {})
        
        if not template_name or not recipient_email:
            return JsonResponse({
                'success': False,
                'error': 'テンプレート名と送信先メールアドレスは必須です'
            }, status=400)
        
        # テスト用のテンプレートを取得
        template = email_service._get_template(template_name)
        if not template:
            return JsonResponse({
                'success': False,
                'error': 'テンプレートが見つかりません'
            }, status=404)
        
        # テストコンテキストを作成
        context = {
            'store_name': 'テスト店舗',
            'owner_name': 'テスト太郎',
            'store_email': 'test@example.com',
            'store_phone': '03-1234-5678',
            'store_address': '東京都テスト区テスト町1-2-3',
            'area_name': 'テストエリア',
            'registration_date': timezone.now().strftime('%Y年%m月%d日 %H:%M'),
            'admin_url': 'http://localhost:8000/admin/',
            **test_context
        }
        
        # テストメール送信
        success = email_service._send_email(
            template=template,
            context=context,
            recipient_email=recipient_email,
            notification=None
        )
        
        return JsonResponse({
            'success': success,
            'message': 'テストメールを送信しました' if success else 'テストメール送信に失敗しました'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)