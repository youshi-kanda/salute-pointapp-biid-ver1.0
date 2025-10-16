"""
meltyアプリとのSSO連携機能

このモジュールはmeltyアプリとのシングルサインオン（SSO）連携、
会員データの同期、ランク優遇機能を提供します。
"""

import requests
import logging
from typing import Dict, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
import jwt
from datetime import datetime, timedelta

User = get_user_model()
logger = logging.getLogger(__name__)

class MeltyIntegrationError(Exception):
    """melty連携エラー"""
    pass

class MeltyAPIClient:
    """melty API クライアント - SSO非対応版"""
    
    def __init__(self):
        # 実際のMELTY APIエンドポイント
        self.base_url = getattr(settings, 'MELTY_API_BASE_URL', 'http://app-melty.com/melty-app_system/api')
        self.api_key = getattr(settings, 'MELTY_API_KEY', '')  # API認証用
        
        if not self.api_key:
            logger.warning("melty API key not configured")
    
    def verify_user_credentials(self, email: str, password: str) -> Dict:
        """MELTY既存ログインAPIを使用して認証・会員情報取得"""
        try:
            # MELTYの既存ログインエンドポイントを使用
            response = requests.post(f"{self.base_url}/login", {
                'email': email,
                'password': password
            }, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                user_data = result.get('user', {})
                
                # 会員種別情報を抽出（複数フィールドに対応）
                membership_type = self._extract_membership_type(user_data)
                
                # ログイン成功時のレスポンスからユーザー情報を抽出
                return {
                    'verified': True,
                    'user_data': user_data,
                    'token': result.get('token', ''),  # MELTYのセッショントークン
                    'user_id': user_data.get('id', ''),
                    'email': user_data.get('email', email),
                    'membership_type': membership_type
                }
            else:
                return {'verified': False, 'error': 'Invalid credentials'}
        except requests.RequestException as e:
            logger.error(f"Failed to verify melty credentials: {str(e)}")
            return {'verified': False, 'error': str(e)}
    
    def _extract_membership_type(self, user_data: Dict) -> str:
        """ユーザーデータから会員種別を抽出"""
        # MELTY APIレスポンスの一般的なフィールドをチェック
        membership_fields = [
            'membership_type',    # "membership_type": "premium"
            'plan',              # "plan": "premium"
            'subscription',      # "subscription": "active"
            'member_type',       # "member_type": "paid"
            'is_premium',        # "is_premium": true
            'is_paid',           # "is_paid": true
            'subscription_status', # "subscription_status": "active"
        ]
        
        for field in membership_fields:
            value = user_data.get(field)
            if value:
                # 文字列の場合は小文字に変換
                str_value = str(value).lower() if value else ''
                
                # 有料会員を示すキーワード
                premium_keywords = ['premium', 'paid', 'active', 'true', 'pro', 'plus']
                if any(keyword in str_value for keyword in premium_keywords):
                    return 'premium'
        
        # デフォルトは無料会員
        return 'free'
    
    def get_user_profile_with_session(self, session_token: str) -> Dict:
        """MELTYセッショントークンでユーザープロフィール取得"""
        try:
            # MELTYの既存プロフィールAPIを使用
            headers = {
                'Authorization': f'Bearer {session_token}',
                'Cookie': f'session_token={session_token}'  # セッションクッキーも設定
            }
            response = requests.get(f"{self.base_url}/profile", headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                # フォールバック: ユーザーダッシュボードの既存エンドポイントを試す
                response = requests.get(f"{self.base_url}/dashboard", headers=headers, timeout=10)
                if response.status_code == 200:
                    # HTMLレスポンスからユーザー情報を抽出（簡単なスクレイピング）
                    return self._extract_user_info_from_html(response.text)
                raise MeltyIntegrationError(f"Profile fetch failed: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"Failed to get melty user profile: {str(e)}")
            raise MeltyIntegrationError(f"Profile fetch failed: {str(e)}")
    
    def check_user_exists_via_password_reset(self, email: str) -> bool:
        """MELTYパスワードリセットAPIでユーザー存在確認"""
        try:
            # パスワードリセットリクエストでユーザー存在を確認
            response = requests.post(f"{self.base_url}/password-reset", {
                'email': email
            }, timeout=10)
            
            # ユーザーが存在する場合は200、存在しない場合は404またはエラーメッセージ
            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                return False
            else:
                # レスポンス内容をチェック
                content = response.text.lower()
                return 'user not found' not in content and 'email not found' not in content
        except requests.RequestException:
            return False
    
    def _extract_user_info_from_html(self, html: str) -> Dict:
        """HTMLレスポンスからユーザー情報を抽出"""
        try:
            import re
            # 簡単な正規表現でユーザー情報を抽出
            user_id_match = re.search(r'user[_\-]?id["\s]*:["\s]*([^"\s,}]+)', html, re.IGNORECASE)
            email_match = re.search(r'email["\s]*:["\s]*([^"\s,}]+)', html, re.IGNORECASE)
            name_match = re.search(r'name["\s]*:["\s]*([^"\s,}]+)', html, re.IGNORECASE)
            
            # 会員種別情報を抽出（複数パターンに対応）
            membership_patterns = [
                r'membership["\s]*:["\s]*([^"\s,}]+)',  # "membership": "premium"
                r'plan["\s]*:["\s]*([^"\s,}]+)',        # "plan": "premium"
                r'subscription["\s]*:["\s]*([^"\s,}]+)', # "subscription": "active"
                r'member_type["\s]*:["\s]*([^"\s,}]+)',  # "member_type": "paid"
                r'is_premium["\s]*:["\s]*(true|false)',  # "is_premium": true
                r'有料会員|プレミアム|有料プラン',          # 日本語パターン
            ]
            
            membership_info = 'free'  # デフォルトは無料会員
            for pattern in membership_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    value = match.group(1).lower()
                    if value in ['premium', 'paid', 'active', 'true'] or '有料' in value or 'プレミアム' in value:
                        membership_info = 'premium'
                        break
            
            return {
                'user_id': user_id_match.group(1) if user_id_match else '',
                'email': email_match.group(1) if email_match else '',
                'name': name_match.group(1) if name_match else '',
                'membership_type': membership_info,
                'extracted_from_html': True
            }
        except Exception as e:
            logger.warning(f"Failed to extract user info from HTML: {str(e)}")
            return {'extracted_from_html': False, 'membership_type': 'free'}

class MeltyUserService:
    """meltyユーザー管理サービス"""
    
    def __init__(self):
        self.api_client = MeltyAPIClient()
    
    def create_biid_account_from_melty(self, email: str, first_name: str, 
                                     last_name: str, melty_password: str) -> Tuple[User, bool]:
        """
        melty認証情報から biidアカウントを作成
        
        Returns:
            Tuple[User, bool]: (ユーザーオブジェクト, 新規作成フラグ)
        """
        try:
            # 1. melty既存ログインAPIで認証
            auth_result = self.api_client.verify_user_credentials(email, melty_password)
            
            if not auth_result or not auth_result.get('verified'):
                raise MeltyIntegrationError("melty authentication failed")
            
            # 2. meltyユーザー情報を取得
            melty_user_data = auth_result.get('user_data', {})
            melty_user_id = auth_result.get('user_id', '') or melty_user_data.get('id', '')
            melty_email = auth_result.get('email', email)
            session_token = auth_result.get('token', '')
            
            # 3. セッショントークンがある場合は詳細プロフィールを取得
            if session_token:
                try:
                    detailed_profile = self.api_client.get_user_profile_with_session(session_token)
                    melty_user_data.update(detailed_profile)
                except Exception as e:
                    logger.warning(f"Failed to get detailed profile: {str(e)}")
            
            if not melty_user_id:
                raise MeltyIntegrationError("melty user ID not found in authentication response")
            
            # 4. 既存のmelty連携アカウントチェック
            existing_user = None
            try:
                existing_user = User.objects.get(melty_user_id=melty_user_id)
                logger.info(f"Found existing melty-linked user: {existing_user.username}")
                return existing_user, False
            except User.DoesNotExist:
                pass
            
            # 5. 同じメールアドレスの既存ユーザーチェック
            try:
                existing_user = User.objects.get(email=melty_email)
                # 既存ユーザーにmelty連携を追加
                return self.link_melty_to_existing_user(existing_user, melty_user_id, melty_user_data), False
            except User.DoesNotExist:
                pass
            
            # 6. 新規biidアカウント作成（MELTY会員種別に応じたランク）
            melty_membership = auth_result.get('membership_type', 'free')
            new_user = self.create_new_biid_user_with_melty(
                email=melty_email,
                first_name=first_name,
                last_name=last_name,
                melty_user_id=melty_user_id,
                melty_profile=melty_user_data,
                melty_membership_type=melty_membership
            )
            
            logger.info(f"Created new biid user from melty: {new_user.username} (Silver rank)")
            return new_user, True
            
        except Exception as e:
            logger.error(f"Failed to create biid account from melty: {str(e)}")
            raise MeltyIntegrationError(f"Account creation failed: {str(e)}")
    
    def create_new_biid_user_with_melty(self, email: str, first_name: str, 
                                       last_name: str, melty_user_id: str, 
                                       melty_profile: Dict, 
                                       melty_membership_type: str = 'free') -> User:
        """melty連携付きの新規biidユーザー作成（会員種別連動）"""
        
        # ユニークなusernameを生成
        base_username = f"{first_name}_{last_name}".lower()
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        
        # MELTY会員種別に応じたmember_idプレフィックスと初期ランク
        import uuid
        if melty_membership_type == 'premium':
            # MELTY有料会員はゴールドランクでスタート
            member_id_prefix = "G"  # Gold
            initial_rank = 'gold'
        else:
            # MELTY無料会員はシルバーランクでスタート
            member_id_prefix = "S"  # Silver 
            initial_rank = 'silver'
        
        member_id = f"{member_id_prefix}{str(uuid.uuid4().hex[:8]).upper()}"
        while User.objects.filter(member_id=member_id).exists():
            member_id = f"{member_id_prefix}{str(uuid.uuid4().hex[:8]).upper()}"
        
        # melty経由ユーザー作成
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            member_id=member_id,
            rank=initial_rank,  # MELTY会員種別に応じたランク
            registration_source='melty',
            melty_user_id=melty_user_id,
            melty_email=email,
            melty_connected_at=timezone.now(),
            is_melty_linked=True,
            melty_profile_data=melty_profile,
            is_active=True
        )
        
        # MELTY会員種別に応じたウェルカムボーナスを付与
        self.grant_melty_welcome_bonus(user, melty_membership_type)
        
        return user
    
    def link_melty_to_existing_user(self, user: User, melty_user_id: str, melty_profile: Dict, melty_membership_type: str = 'free') -> User:
        """既存ユーザーにmelty連携を追加（会員種別連動）"""
        user.melty_user_id = melty_user_id
        user.melty_email = melty_profile.get('email')
        user.melty_connected_at = timezone.now()
        user.is_melty_linked = True
        user.melty_profile_data = melty_profile
        
        # MELTY会員種別に応じたランクアップグレード
        original_rank = user.rank
        rank_upgraded = False
        
        if melty_membership_type == 'premium':
            # MELTY有料会員の場合、ゴールドランクにアップグレード
            if user.rank in ['bronze', 'silver']:
                user.rank = 'gold'
                rank_upgraded = True
                self.grant_melty_welcome_bonus(user, melty_membership_type)
                logger.info(f"Upgraded user {user.username} from {original_rank} to Gold via MELTY Premium link")
        else:
            # MELTY無料会員の場合、シルバーランクにアップグレード（ブロンズから）
            if user.rank == 'bronze':
                user.rank = 'silver'
                rank_upgraded = True
                self.grant_melty_welcome_bonus(user, melty_membership_type)
                logger.info(f"Upgraded user {user.username} from Bronze to Silver via MELTY Free link")
        
        if not rank_upgraded:
            logger.info(f"User {user.username} melty link completed - no rank upgrade needed (current: {user.rank})")
        
        user.save()
        return user
    
    def grant_melty_welcome_bonus(self, user: User, melty_membership_type: str = 'free'):
        """MELTY会員種別に応じたウェルカムボーナス付与"""
        try:
            if melty_membership_type == 'premium':
                # MELTY有料会員：ゴールドランク特典
                bonus_points = 2000  # 2000ポイント
                expiry_months = 18   # 18ヶ月有効
                source_description = "MELTYプレミアム会員限定ウェルカムボーナス【ゴールド特典】"
                logger.info(f"Granted MELTY Premium welcome bonus {bonus_points}pt to user {user.username} (Gold rank)")
            else:
                # MELTY無料会員：シルバーランク特典
                bonus_points = 1000  # 1000ポイント
                expiry_months = 12   # 12ヶ月有効
                source_description = "MELTYアプリ連携ウェルカムボーナス【シルバー特典】"
                logger.info(f"Granted MELTY Free welcome bonus {bonus_points}pt to user {user.username} (Silver rank)")
            
            user.add_points(
                points=bonus_points,
                expiry_months=expiry_months,
                source_description=source_description
            )
            
        except Exception as e:
            logger.error(f"Failed to grant melty welcome bonus: {str(e)}")
    
    def sync_melty_profile(self, user: User) -> bool:
        """meltyプロフィール情報を同期"""
        try:
            if not user.is_melty_linked or not user.melty_user_id:
                return False
            
            melty_profile = self.api_client.get_user_profile(user.melty_user_id)
            
            # プロフィール情報を更新
            user.melty_profile_data = melty_profile
            
            # メールアドレスが変更されている場合は更新
            melty_email = melty_profile.get('email')
            if melty_email and melty_email != user.melty_email:
                user.melty_email = melty_email
            
            user.save()
            logger.info(f"Synced melty profile for user {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync melty profile: {str(e)}")
            return False
    
    def unlink_melty_account(self, user: User) -> bool:
        """meltyアカウント連携を解除"""
        try:
            user.melty_user_id = None
            user.melty_email = None
            user.melty_connected_at = None
            user.is_melty_linked = False
            user.melty_profile_data = {}
            user.save()
            
            logger.info(f"Unlinked melty account for user {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unlink melty account: {str(e)}")
            return False

class MeltyDirectAuth:
    """melty 直接認証方式（SSO非対応版）"""
    
    def __init__(self):
        self.api_client = MeltyAPIClient()
        self.user_service = MeltyUserService()
    
    def authenticate_user(self, email: str, password: str) -> Tuple[User, bool]:
        """
        melty認証情報でユーザー認証
        
        Returns:
            Tuple[User, bool]: (ユーザーオブジェクト, 新規作成フラグ)
        """
        try:
            # melty既存ログインAPIで認証
            auth_result = self.api_client.verify_user_credentials(email, password)
            
            if not auth_result or not auth_result.get('verified'):
                raise MeltyIntegrationError("melty authentication failed")
            
            # ユーザーIDを取得
            melty_user_id = auth_result.get('user_id', '') or auth_result.get('user_data', {}).get('id', '')
            
            # 既存のmelty連携ユーザーを探す
            try:
                if melty_user_id:
                    user = User.objects.get(melty_user_id=melty_user_id)
                else:
                    # melty_user_idが取得できない場合はメールで検索
                    user = User.objects.get(email=email, is_melty_linked=True)
                
                logger.info(f"melty direct auth login: {user.username}")
                return user, False
            except User.DoesNotExist:
                # 新規ユーザーの場合は登録が必要
                raise MeltyIntegrationError("User not found - registration required")
                
        except Exception as e:
            logger.error(f"melty direct auth failed: {str(e)}")
            raise MeltyIntegrationError(f"Direct auth failed: {str(e)}")
    
    def verify_email_exists(self, email: str) -> bool:
        """meltyアカウントのメール存在確認"""
        return self.api_client.check_user_exists_via_password_reset(email)

# サービスインスタンス
melty_direct_auth = MeltyDirectAuth()
melty_user_service = MeltyUserService()
melty_api_client = MeltyAPIClient()