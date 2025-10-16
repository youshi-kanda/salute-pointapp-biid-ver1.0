"""
meltyアプリ連携用のAPIビュー
"""

from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model, login
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect
import logging

from .melty_integration import melty_direct_auth, melty_user_service, MeltyIntegrationError
from .serializers import UserSerializer

User = get_user_model()
logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def melty_auth_url(request):
    """melty OAuth認証URL取得"""
    try:
        # CSRF対策のためのstate生成
        import secrets
        state = secrets.token_urlsafe(32)
        request.session['melty_oauth_state'] = state
        
        auth_url = melty_direct_auth.generate_auth_url(state=state)
        
        return Response({
            'success': True,
            'auth_url': auth_url,
            'state': state
        })
    except Exception as e:
        logger.error(f"Failed to generate melty auth URL: {str(e)}")
        return Response({
            'success': False,
            'error': 'Auth URL generation failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def melty_callback(request):
    """melty OAuth コールバック処理"""
    try:
        # パラメータ取得
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            logger.warning(f"melty OAuth error: {error}")
            return HttpResponseRedirect(f"/user/login?error=melty_auth_failed")
        
        if not code:
            return HttpResponseRedirect(f"/user/login?error=missing_code")
        
        # state検証
        session_state = request.session.get('melty_oauth_state')
        if not session_state or session_state != state:
            logger.warning("melty OAuth state mismatch")
            return HttpResponseRedirect(f"/user/login?error=state_mismatch")
        
        # melty SSO処理
        try:
            user, access_token = melty_direct_auth.handle_callback(code, state)
            
            # Django認証
            login(request, user)
            
            # セッション情報をクリア
            request.session.pop('melty_oauth_state', None)
            
            logger.info(f"melty SSO successful for user: {user.username}")
            return HttpResponseRedirect("/user?melty_login=success")
            
        except MeltyIntegrationError as e:
            if "registration required" in str(e):
                # 新規ユーザーの場合は登録画面へ
                return HttpResponseRedirect(f"/user/register?source=melty&code={code}")
            else:
                logger.error(f"melty SSO failed: {str(e)}")
                return HttpResponseRedirect(f"/user/login?error=melty_sso_failed")
        
    except Exception as e:
        logger.error(f"melty callback error: {str(e)}")
        return HttpResponseRedirect(f"/user/login?error=callback_error")

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_with_melty(request):
    """melty経由での新規登録"""
    try:
        # リクエストデータ取得
        melty_user_id = request.data.get('melty_user_id')
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        melty_password = request.data.get('melty_password')
        
        if not all([melty_user_id, email, first_name, last_name, melty_password]):
            return Response({
                'success': False,
                'error': '必須項目が不足しています'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # melty経由でbiidアカウント作成
        user, is_new = melty_user_service.create_biid_account_from_melty(
            melty_user_id=melty_user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            melty_password=melty_password
        )
        
        # Django認証
        login(request, user)
        
        # ユーザー情報をシリアライズ
        serializer = UserSerializer(user)
        
        return Response({
            'success': True,
            'user': serializer.data,
            'is_new_user': is_new,
            'rank': user.rank,
            'welcome_bonus': 1000 if is_new else 0,
            'message': 'melty連携でのアカウント作成が完了しました' if is_new else 'meltyアカウントにリンクしました'
        }, status=status.HTTP_201_CREATED if is_new else status.HTTP_200_OK)
        
    except MeltyIntegrationError as e:
        logger.error(f"melty registration failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Unexpected melty registration error: {str(e)}")
        return Response({
            'success': False,
            'error': '登録処理中にエラーが発生しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_direct(request):
    """biid直接登録（ブロンズランク）"""
    try:
        # リクエストデータ取得
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        
        if not all([email, password, first_name, last_name]):
            return Response({
                'success': False,
                'error': '必須項目が不足しています'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 既存ユーザーチェック
        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'error': 'このメールアドレスは既に登録されています'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ユニークなusernameを生成
        base_username = f"{first_name}_{last_name}".lower()
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        
        # ユニークなmember_idを生成
        import uuid
        member_id = f"B{str(uuid.uuid4().hex[:8]).upper()}"
        while User.objects.filter(member_id=member_id).exists():
            member_id = f"B{str(uuid.uuid4().hex[:8]).upper()}"
        
        # 直接登録ユーザーはブロンズランクでスタート
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            member_id=member_id,
            rank='bronze',  # 直接登録はブロンズランク
            registration_source='direct',
            is_active=True
        )
        
        # 基本ウェルカムボーナス（ブロンズランク）
        user.add_points(
            points=500,
            expiry_months=6,
            source_description="biid新規登録ウェルカムボーナス"
        )
        
        # Django認証
        login(request, user)
        
        # ユーザー情報をシリアライズ
        serializer = UserSerializer(user)
        
        logger.info(f"New direct registration: {user.username} (Bronze rank)")
        
        return Response({
            'success': True,
            'user': serializer.data,
            'is_new_user': True,
            'rank': user.rank,
            'welcome_bonus': 500,
            'message': 'biidアカウントの作成が完了しました'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Direct registration failed: {str(e)}")
        return Response({
            'success': False,
            'error': '登録処理中にエラーが発生しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def link_melty_account(request):
    """既存biidアカウントにmeltyアカウントをリンク"""
    try:
        melty_code = request.data.get('melty_code')
        
        if not melty_code:
            return Response({
                'success': False,
                'error': 'melty認証コードが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        if user.is_melty_linked:
            return Response({
                'success': False,
                'error': '既にmeltyアカウントとリンクされています'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # meltyアカウント情報を取得してリンク
        token_data = melty_user_service.api_client.exchange_code_for_token(melty_code)
        access_token = token_data.get('access_token')
        
        if not access_token:
            return Response({
                'success': False,
                'error': 'melty認証に失敗しました'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        melty_profile = melty_user_service.api_client.get_user_profile(access_token)
        melty_user_id = melty_profile.get('user_id')
        
        # 他のユーザーが同じmeltyアカウントを使用していないかチェック
        if User.objects.filter(melty_user_id=melty_user_id).exists():
            return Response({
                'success': False,
                'error': 'このmeltyアカウントは既に他のbiidアカウントとリンクされています'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # リンク実行
        melty_user_service.link_melty_to_existing_user(user, melty_user_id, melty_profile)
        
        # ユーザー情報を更新して返す
        user.refresh_from_db()
        serializer = UserSerializer(user)
        
        rank_upgrade = user.rank == 'silver'
        
        return Response({
            'success': True,
            'user': serializer.data,
            'rank_upgraded': rank_upgrade,
            'new_rank': user.rank,
            'welcome_bonus': 1000 if rank_upgrade else 0,
            'message': 'meltyアカウントとのリンクが完了しました'
        })
        
    except MeltyIntegrationError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"melty account linking failed: {str(e)}")
        return Response({
            'success': False,
            'error': 'リンク処理中にエラーが発生しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unlink_melty_account(request):
    """meltyアカウントリンクを解除"""
    try:
        user = request.user
        
        if not user.is_melty_linked:
            return Response({
                'success': False,
                'error': 'meltyアカウントとリンクされていません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # リンク解除
        success = melty_user_service.unlink_melty_account(user)
        
        if success:
            user.refresh_from_db()
            serializer = UserSerializer(user)
            
            return Response({
                'success': True,
                'user': serializer.data,
                'message': 'meltyアカウントとのリンクを解除しました'
            })
        else:
            return Response({
                'success': False,
                'error': 'リンク解除に失敗しました'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"melty account unlinking failed: {str(e)}")
        return Response({
            'success': False,
            'error': 'リンク解除処理中にエラーが発生しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def melty_profile_sync(request):
    """meltyプロフィール同期"""
    try:
        user = request.user
        
        if not user.is_melty_linked:
            return Response({
                'success': False,
                'error': 'meltyアカウントとリンクされていません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # アクセストークンが必要だが、簡易実装では省略
        # 実際の実装では、保存されたrefresh_tokenから新しいaccess_tokenを取得
        
        return Response({
            'success': True,
            'melty_profile': user.melty_profile_data,
            'linked_at': user.melty_connected_at,
            'message': 'meltyプロフィール情報を取得しました'
        })
        
    except Exception as e:
        logger.error(f"melty profile sync failed: {str(e)}")
        return Response({
            'success': False,
            'error': 'プロフィール同期中にエラーが発生しました'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)