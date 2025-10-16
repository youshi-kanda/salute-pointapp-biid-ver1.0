from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
import jwt
import pyotp
import qrcode
from io import BytesIO
import base64
import secrets

User = get_user_model()


class RoleBasedLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        role = request.data.get('role')
        two_factor_token = request.data.get('token')  # 2FA用
        
        if not email or not password or not role:
            return Response({
                'success': False,
                'error': 'メールアドレス、パスワード、ロールが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ユーザー認証
        user = None
        try:
            if '@' in email:
                user_obj = User.objects.get(email=email)
                user = authenticate(username=user_obj.username, password=password)
            else:
                user = authenticate(username=email, password=password)
        except User.DoesNotExist:
            user = authenticate(username=email, password=password)
        
        if not user:
            return Response({
                'success': False,
                'error': '認証に失敗しました'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # ロール確認
        if user.role != role:
            return Response({
                'success': False,
                'error': '指定されたロールでのログインはできません'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # アカウント状態確認
        if user.status != 'active':
            return Response({
                'success': False,
                'error': 'アカウントが無効化されています'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 2FA確認
        if user.is_2fa_enabled:
            if not two_factor_token:
                return Response({
                    'success': False,
                    'error': '2FA認証が必要です',
                    'requires_2fa': True
                }, status=status.HTTP_200_OK)
            
            # 2FAトークン検証
            totp = pyotp.TOTP(user.two_factor_secret)
            if not totp.verify(two_factor_token, valid_window=1):
                # バックアップコードも確認
                if two_factor_token not in user.backup_codes:
                    return Response({
                        'success': False,
                        'error': '2FA認証に失敗しました'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                else:
                    # バックアップコードを使用した場合は削除
                    user.backup_codes.remove(two_factor_token)
                    user.save()
        
        # JWT トークン生成
        access_payload = {
            'user_id': user.id,
            'role': user.role,
            'permissions': self.get_permissions_for_role(user.role),
            'store_id': user.store.id if user.store else None,
            'exp': datetime.utcnow() + timedelta(minutes=15)
        }
        
        refresh_payload = {
            'user_id': user.id,
            'role': user.role,
            'exp': datetime.utcnow() + timedelta(days=7)
        }
        
        access_token = jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        refresh_token = jwt.encode(refresh_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        
        # 最終ログイン時刻を更新
        user.last_login_date = timezone.now()
        user.save()
        
        return Response({
            'success': True,
            'data': {
                'tokens': {
                    'access': access_token,
                    'refresh': refresh_token,
                    'expiresIn': 900  # 15分
                },
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'is_staff': user.is_staff,
                    'is_active': user.is_active,
                    'permissions': self.get_permissions_for_role(user.role),
                    'store_id': user.store.id if user.store else None,
                    'store_name': user.store.name if user.store else None,
                    'created_at': user.registration_date.isoformat()
                }
            },
            'message': 'ログイン成功'
        })
    
    def get_permissions_for_role(self, role):
        """ロール別権限取得"""
        permissions = {
            'customer': [
                'user.view_profile',
                'user.update_profile',
                'user.view_points',
                'user.charge_points',
                'user.view_transactions',
                'user.exchange_gifts',
                'user.view_stores'
            ],
            'store_manager': [
                'store.view_dashboard',
                'store.manage_points',
                'store.view_transactions',
                'store.generate_receipts',
                'store.manage_cards',
                'store.view_customers'
            ],
            'admin': [
                'admin.view_dashboard',
                'admin.manage_users',
                'admin.manage_stores',
                'admin.view_transactions',
                'admin.generate_reports',
                'admin.manage_gifts',
                'admin.system_settings'
            ],
            'terminal': [
                'terminal.process_payment',
                'terminal.charge_points',
                'terminal.lookup_user',
                'terminal.view_status'
            ]
        }
        return permissions.get(role, [])


class CustomerLoginView(RoleBasedLoginView):
    def post(self, request):
        request.data['role'] = 'customer'
        return super().post(request)


class StoreLoginView(RoleBasedLoginView):
    def post(self, request):
        request.data['role'] = 'store_manager'
        return super().post(request)


class AdminLoginView(RoleBasedLoginView):
    def post(self, request):
        request.data['role'] = 'admin'
        return super().post(request)


class TerminalLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        terminal_id = request.data.get('terminalId')
        access_code = request.data.get('accessCode')
        
        if not terminal_id or not access_code:
            return Response({
                'success': False,
                'error': '端末IDとアクセスコードが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 端末認証（実際の実装では専用のTerminalモデルを使用）
        try:
            user = User.objects.get(username=terminal_id, role='terminal')
            if not user.check_password(access_code):
                raise User.DoesNotExist()
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': '端末認証に失敗しました'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # JWT トークン生成
        access_payload = {
            'user_id': user.id,
            'role': 'terminal',
            'terminal_id': terminal_id,
            'store_id': user.store.id if user.store else None,
            'permissions': ['terminal.process_payment', 'terminal.charge_points', 'terminal.lookup_user'],
            'exp': datetime.utcnow() + timedelta(hours=8)  # 端末は長時間有効
        }
        
        access_token = jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        
        return Response({
            'success': True,
            'data': {
                'tokens': {
                    'access': access_token,
                    'expiresIn': 28800  # 8時間
                },
                'terminal': {
                    'id': terminal_id,
                    'store_id': user.store.id if user.store else None,
                    'store_name': user.store.name if user.store else None,
                    'permissions': ['terminal.process_payment', 'terminal.charge_points', 'terminal.lookup_user']
                }
            },
            'message': '端末認証成功'
        })


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({
                'success': False,
                'error': 'リフレッシュトークンが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get('user_id')
            role = payload.get('role')
            
            user = User.objects.get(id=user_id)
            
            access_payload = {
                'user_id': user_id,
                'role': role,
                'permissions': RoleBasedLoginView().get_permissions_for_role(role),
                'store_id': user.store.id if user.store else None,
                'exp': datetime.utcnow() + timedelta(minutes=15)
            }
            
            access_token = jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
            
            return Response({
                'success': True,
                'data': {
                    'access': access_token,
                    'expiresIn': 900
                }
            })
        except jwt.ExpiredSignatureError:
            return Response({
                'success': False,
                'error': 'リフレッシュトークンが期限切れです'
            }, status=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return Response({
                'success': False,
                'error': '無効なリフレッシュトークンです'
            }, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'ユーザーが見つかりません'
            }, status=status.HTTP_404_NOT_FOUND)


class LogoutView(APIView):
    def post(self, request):
        # 実際の実装では、トークンをブラックリストに追加
        return Response({
            'success': True,
            'message': 'ログアウトしました'
        })


class TwoFactorSetupView(APIView):
    def post(self, request):
        user = request.user
        
        if user.is_2fa_enabled:
            return Response({
                'success': False,
                'error': '2FAは既に有効化されています'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 秘密鍵生成
        secret = pyotp.random_base32()
        
        # QRコード生成
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="biid Point System"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
        
        # バックアップコード生成
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        
        # 一時的に保存（実際の有効化は別のエンドポイントで）
        user.two_factor_secret = secret
        user.backup_codes = backup_codes
        user.save()
        
        return Response({
            'success': True,
            'qr_code_url': f'data:image/png;base64,{qr_code_data}',
            'backup_codes': backup_codes,
            'secret': secret
        })
    
    def put(self, request):
        """2FA有効化"""
        user = request.user
        token = request.data.get('token')
        
        if not token:
            return Response({
                'success': False,
                'error': '認証トークンが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not user.two_factor_secret:
            return Response({
                'success': False,
                'error': '2FA設定が開始されていません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # トークン検証
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(token, valid_window=1):
            return Response({
                'success': False,
                'error': '認証トークンが正しくありません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 2FA有効化
        user.is_2fa_enabled = True
        user.save()
        
        return Response({
            'success': True,
            'message': '2FAが有効化されました'
        })


class TwoFactorStatusView(APIView):
    def get(self, request):
        user = request.user
        return Response({
            'success': True,
            'data': {
                'is_enabled': user.is_2fa_enabled,
                'backup_codes_count': len(user.backup_codes)
            }
        })


class TwoFactorDisableView(APIView):
    def post(self, request):
        user = request.user
        password = request.data.get('password')
        
        if not password:
            return Response({
                'success': False,
                'error': 'パスワードが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not user.check_password(password):
            return Response({
                'success': False,
                'error': 'パスワードが正しくありません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 2FA無効化
        user.is_2fa_enabled = False
        user.two_factor_secret = ''
        user.backup_codes = []
        user.save()
        
        return Response({
            'success': True,
            'message': '2FAが無効化されました'
        })


class GenerateBackupCodesView(APIView):
    def post(self, request):
        user = request.user
        
        if not user.is_2fa_enabled:
            return Response({
                'success': False,
                'error': '2FAが有効化されていません'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 新しいバックアップコード生成
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        user.backup_codes = backup_codes
        user.save()
        
        return Response({
            'success': True,
            'backup_codes': backup_codes
        })


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({
                'success': False,
                'error': 'メールアドレスが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            
            # パスワードリセットトークン生成
            reset_token = secrets.token_urlsafe(32)
            
            # 実際の実装では、リセットトークンをデータベースに保存し、メール送信
            # ここではモックレスポンス
            
            return Response({
                'success': True,
                'message': 'パスワードリセット用のメールを送信しました',
                'reset_token': reset_token  # 開発用（本番では削除）
            })
        except User.DoesNotExist:
            # セキュリティ上、ユーザーが存在しない場合も成功レスポンス
            return Response({
                'success': True,
                'message': 'パスワードリセット用のメールを送信しました'
            })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        token = request.data.get('token')
        password = request.data.get('password')
        
        if not token or not password:
            return Response({
                'success': False,
                'error': 'トークンとパスワードが必要です'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 実際の実装では、トークンの検証とパスワード更新
        # ここではモックレスポンス
        
        return Response({
            'success': True,
            'message': 'パスワードがリセットされました'
        })