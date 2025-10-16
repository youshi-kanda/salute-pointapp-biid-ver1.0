# Generated migration for 5-category settings models - Production ready
# 本番運用仕様 5カテゴリ設定モデル追加マイグレーション

from django.db import migrations, models
import django.core.validators
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),  # 0001_initialの次として実行
    ]

    operations = [
        # 🏗️ システム基盤設定モデル追加
        migrations.CreateModel(
            name='SystemInfrastructureSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_name', models.CharField(default='BIID Point Management System', help_text='全インターフェース共通のシステム名称', max_length=100, verbose_name='システム名')),
                ('site_description', models.TextField(blank=True, default='エンタープライズ級ポイント管理プラットフォーム', help_text='システム概要・メタ情報', verbose_name='システム説明')),
                ('system_version', models.CharField(default='2.0.0', help_text='現在運用中のシステムバージョン', max_length=20, verbose_name='システムバージョン')),
                ('system_support_email', models.EmailField(default='admin@biid-system.com', help_text='システム管理・技術サポート用連絡先', max_length=254, validators=[django.core.validators.EmailValidator()], verbose_name='システム管理者メール')),
                ('emergency_contact', models.CharField(default='080-1234-5678', help_text='システム障害時の緊急連絡先', max_length=50, verbose_name='緊急連絡先')),
                ('organization_name', models.CharField(default='BIID Systems Inc.', help_text='システム運営組織の正式名称', max_length=100, verbose_name='運営組織名')),
                ('operation_region', models.CharField(default='関西域（大阪・京都・神戸）', help_text='システム運営対象地域', max_length=100, verbose_name='運営地域')),
                ('timezone', models.CharField(choices=[('Asia/Tokyo', 'Asia/Tokyo'), ('UTC', 'UTC'), ('Asia/Seoul', 'Asia/Seoul')], default='Asia/Tokyo', help_text='全システムの時刻表示・処理に影響', max_length=50, verbose_name='タイムゾーン')),
                ('maintenance_mode', models.BooleanField(default=False, help_text='全システムアクセスを制御', verbose_name='メンテナンスモード')),
                ('debug_mode', models.BooleanField(default=False, help_text='システム全体のログレベル・エラー表示を制御', verbose_name='デバッグモード')),
                ('maintenance_message', models.TextField(blank=True, default='現在システムメンテナンス中です。しばらくお待ちください。', help_text='メンテナンス画面で表示されるメッセージ', verbose_name='メンテナンスメッセージ')),
                ('maintenance_start_time', models.DateTimeField(blank=True, null=True, verbose_name='メンテナンス開始時刻')),
                ('maintenance_end_time', models.DateTimeField(blank=True, null=True, verbose_name='メンテナンス終了予定時刻')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='更新者')),
            ],
            options={
                'verbose_name': '🏗️ システム基盤設定',
                'verbose_name_plural': '🏗️ システム基盤設定',
                'db_table': 'core_system_infrastructure_settings',
            },
        ),
        
        # 🔒 セキュリティ設定モデル追加
        migrations.CreateModel(
            name='SecuritySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('max_login_attempts', models.IntegerField(default=5, help_text='アカウントロック前の最大ログイン試行回数', validators=[django.core.validators.MinValueValidator(3), django.core.validators.MaxValueValidator(20)], verbose_name='最大ログイン試行回数')),
                ('login_lockout_duration_minutes', models.IntegerField(default=30, help_text='アカウントロック時間', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(1440)], verbose_name='ロック時間（分）')),
                ('session_timeout_minutes', models.IntegerField(default=60, help_text='ログインセッションの有効時間', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(480)], verbose_name='セッション有効時間（分）')),
                ('api_rate_limit_per_minute', models.IntegerField(default=100, help_text='1分間あたりのAPI呼出制限', validators=[django.core.validators.MinValueValidator(10), django.core.validators.MaxValueValidator(1000)], verbose_name='API制限/分')),
                ('api_rate_limit_per_hour', models.IntegerField(default=1000, help_text='1時間あたりのAPI呼出制限', validators=[django.core.validators.MinValueValidator(100), django.core.validators.MaxValueValidator(10000)], verbose_name='API制限/時')),
                ('enable_ip_whitelist', models.BooleanField(default=False, help_text='管理者ログインのIP制限機能', verbose_name='IP制限有効')),
                ('allowed_ip_addresses', models.TextField(blank=True, help_text='許可IP（カンマ区切り、CIDR対応）', verbose_name='許可IPアドレス')),
                ('enforce_2fa_for_admin', models.BooleanField(default=True, help_text='管理者への2FA強制', verbose_name='管理者2FA強制')),
                ('enforce_2fa_for_store', models.BooleanField(default=False, help_text='店舗管理者への2FA強制', verbose_name='店舗2FA強制')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '🔒 セキュリティ設定',
                'verbose_name_plural': '🔒 セキュリティ設定',
                'db_table': 'core_security_settings',
            },
        ),
        
        # 🔗 決済・外部連携設定モデル追加
        migrations.CreateModel(
            name='ExternalIntegrationSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fincode_api_key', models.CharField(default='', help_text='本番環境用APIキー（要暗号化保存）', max_length=200, verbose_name='FINCODE APIキー')),
                ('fincode_secret_key', models.CharField(blank=True, help_text='本番環境用シークレットキー（要暗号化保存）', max_length=200, verbose_name='FINCODE シークレットキー')),
                ('fincode_shop_id', models.CharField(default='', help_text='契約ショップID', max_length=100, verbose_name='FINCODE ショップID')),
                ('fincode_is_production', models.BooleanField(default=True, help_text='本番運用時はTrue必須', verbose_name='FINCODE 本番環境')),
                ('fincode_webhook_url', models.URLField(blank=True, help_text='決済結果通知受信URL', verbose_name='FINCODE Webhook URL')),
                ('fincode_connection_timeout', models.IntegerField(default=30, help_text='API通信タイムアウト設定', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(120)], verbose_name='FINCODE接続タイムアウト（秒）')),
                ('melty_api_base_url', models.URLField(default='https://api.melty-system.com/v2/', help_text='MELTY連携API接続先', verbose_name='MELTY API ベースURL')),
                ('melty_api_key', models.CharField(blank=True, help_text='MELTY連携認証キー（要暗号化保存）', max_length=200, verbose_name='MELTY APIキー')),
                ('melty_connection_enabled', models.BooleanField(default=True, help_text='MELTY システムとの連携機能', verbose_name='MELTY連携有効')),
                ('melty_sync_interval_minutes', models.IntegerField(default=60, help_text='会員情報同期間隔', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(1440)], verbose_name='MELTY同期間隔（分）')),
                ('external_api_retry_count', models.IntegerField(default=3, help_text='通信失敗時の自動再試行回数', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)], verbose_name='外部API再試行回数')),
                ('external_api_timeout_seconds', models.IntegerField(default=30, help_text='外部システム通信タイムアウト', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(300)], verbose_name='外部API全般タイムアウト（秒）')),
                ('payment_timeout_seconds', models.IntegerField(default=300, help_text='決済処理全体のタイムアウト', validators=[django.core.validators.MinValueValidator(60), django.core.validators.MaxValueValidator(1800)], verbose_name='決済タイムアウト（秒）')),
                ('max_payment_amount', models.DecimalField(decimal_places=2, default=1000000.00, help_text='1回の決済での上限金額', max_digits=10, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10000000.00)], verbose_name='最大決済金額（円）')),
                ('min_payment_amount', models.DecimalField(decimal_places=2, default=100.00, help_text='1回の決済での下限金額', max_digits=10, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100000.00)], verbose_name='最小決済金額（円）')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '🔗 決済・外部連携設定',
                'verbose_name_plural': '🔗 決済・外部連携設定',
                'db_table': 'core_external_integration_settings',
            },
        ),
        
        # 📧 通知・メール設定モデル追加
        migrations.CreateModel(
            name='NotificationSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('smtp_host', models.CharField(default='smtp.sendgrid.net', help_text='メール送信サーバーのホスト名', max_length=255, verbose_name='SMTPホスト')),
                ('smtp_port', models.IntegerField(default=587, help_text='SMTP接続ポート（TLS: 587, SSL: 465）', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(65535)], verbose_name='SMTPポート')),
                ('smtp_username', models.CharField(blank=True, help_text='SMTP認証用ユーザー名', max_length=255, verbose_name='SMTPユーザー名')),
                ('smtp_password', models.CharField(blank=True, help_text='SMTP認証用パスワード（要暗号化保存）', max_length=255, verbose_name='SMTPパスワード')),
                ('smtp_use_tls', models.BooleanField(default=True, help_text='STARTTLS使用（推奨）', verbose_name='TLS使用')),
                ('smtp_use_ssl', models.BooleanField(default=False, help_text='SSL直接接続（TLSと排他）', verbose_name='SSL使用')),
                ('from_email', models.EmailField(default='no-reply@biid-system.com', help_text='送信者メールアドレス', max_length=254, validators=[django.core.validators.EmailValidator()], verbose_name='送信者メール')),
                ('from_name', models.CharField(default='BIID Point System', help_text='送信者名', max_length=100, verbose_name='送信者名')),
                ('reply_to_email', models.EmailField(blank=True, help_text='ユーザーが返信する際の宛先（空白時はfrom_emailを使用）', max_length=254, validators=[django.core.validators.EmailValidator()], verbose_name='返信先メールアドレス')),
                ('enable_welcome_email', models.BooleanField(default=True, help_text='新規ユーザー登録完了メール', verbose_name='ウェルカムメール')),
                ('enable_point_notification', models.BooleanField(default=True, help_text='ポイント付与・消費・有効期限通知', verbose_name='ポイント通知')),
                ('enable_gift_notification', models.BooleanField(default=True, help_text='ギフト交換・受取り・期限通知', verbose_name='ギフト通知')),
                ('enable_promotion_email', models.BooleanField(default=True, help_text='店舗からのプロモーション・キャンペーン通知', verbose_name='プロモーションメール')),
                ('enable_security_notification', models.BooleanField(default=True, help_text='ログイン・パスワード変更・2FA設定通知', verbose_name='セキュリティ通知')),
                ('enable_transaction_notification', models.BooleanField(default=True, help_text='決済・送金・チャージ完了通知', verbose_name='取引通知')),
                ('email_batch_size', models.IntegerField(default=100, help_text='一度に送信するメール数', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(1000)], verbose_name='バッチ送信数')),
                ('email_rate_limit_per_hour', models.IntegerField(default=1000, help_text='1時間あたりの最大メール送信数', validators=[django.core.validators.MinValueValidator(10), django.core.validators.MaxValueValidator(10000)], verbose_name='時間あたり送信制限')),
                ('email_queue_retry_count', models.IntegerField(default=3, help_text='メール送信失敗時の再試行回数', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)], verbose_name='送信再試行回数')),
                ('email_queue_retry_delay_minutes', models.IntegerField(default=5, help_text='メール送信再試行の間隔', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(60)], verbose_name='再試行間隔（分）')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '📧 通知・メール設定',
                'verbose_name_plural': '📧 通知・メール設定',
                'db_table': 'core_notification_settings',
            },
        ),
        
        # 💼 事業運営設定モデル追加
        migrations.CreateModel(
            name='BusinessOperationSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default_point_rate', models.DecimalField(decimal_places=2, default=1.0, help_text='標準的なポイント付与率', max_digits=5, validators=[django.core.validators.MinValueValidator(0.1), django.core.validators.MaxValueValidator(10.0)], verbose_name='基本ポイント還元率（%）')),
                ('point_expiry_months', models.IntegerField(default=12, help_text='付与ポイントの有効期限', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(60)], verbose_name='ポイント有効期限（月）')),
                ('max_point_balance', models.DecimalField(decimal_places=0, default=1000000, help_text='1ユーザーあたりの最大保有ポイント', max_digits=12, validators=[django.core.validators.MinValueValidator(10000), django.core.validators.MaxValueValidator(10000000)], verbose_name='最大ポイント保有数')),
                ('store_deposit_required', models.DecimalField(decimal_places=2, default=100000.00, help_text='店舗開始時に必要なデポジット金額', max_digits=10, validators=[django.core.validators.MinValueValidator(10000), django.core.validators.MaxValueValidator(10000000)], verbose_name='店舗デポジット必要額（円）')),
                ('store_minimum_transaction', models.DecimalField(decimal_places=2, default=50000.00, help_text='店舗での最小決済金額', max_digits=10, validators=[django.core.validators.MinValueValidator(1000), django.core.validators.MaxValueValidator(1000000)], verbose_name='店舗最小決済額（円）')),
                ('store_refund_rate', models.DecimalField(decimal_places=2, default=95.0, help_text='店舗への払戻時の還元率', max_digits=5, validators=[django.core.validators.MinValueValidator(50.0), django.core.validators.MaxValueValidator(100.0)], verbose_name='店舗払戻還元率（%）')),
                ('system_fee_rate', models.DecimalField(decimal_places=2, default=3.0, help_text='システム利用料率', max_digits=5, validators=[django.core.validators.MinValueValidator(0.1), django.core.validators.MaxValueValidator(20.0)], verbose_name='システム手数料率（%）')),
                ('payment_processing_fee', models.DecimalField(decimal_places=2, default=300.00, help_text='1件あたりの決済処理手数料', max_digits=8, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10000)], verbose_name='決済処理手数料（円）')),
                ('transfer_fee', models.DecimalField(decimal_places=2, default=200.00, help_text='ポイント送金時の手数料', max_digits=8, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5000)], verbose_name='送金手数料（円）')),
                ('bank_transfer_fee', models.DecimalField(decimal_places=2, default=330.00, help_text='銀行振込時の手数料', max_digits=8, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(2000)], verbose_name='銀行振込手数料（円）')),
                ('promotion_email_cost', models.DecimalField(decimal_places=2, default=15.00, help_text='1通あたりのプロモーションメール送信コスト', max_digits=6, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(1000)], verbose_name='プロモーションメール送信料（円）')),
                ('minimum_cashout_amount', models.DecimalField(decimal_places=2, default=30000.00, help_text='現金化可能な最小金額', max_digits=10, validators=[django.core.validators.MinValueValidator(1000), django.core.validators.MaxValueValidator(1000000)], verbose_name='最小出金額（円）')),
                ('point_unit_price', models.DecimalField(decimal_places=2, default=1.00, help_text='1ポイントあたりの基本価格', max_digits=6, validators=[django.core.validators.MinValueValidator(0.5), django.core.validators.MaxValueValidator(5.0)], verbose_name='基本ポイント単価（円）')),
                ('tax_rate', models.DecimalField(decimal_places=2, default=10.00, help_text='ポイント購入時の消費税率', max_digits=4, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(30)], verbose_name='消費税率（%）')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '💼 事業運営設定',
                'verbose_name_plural': '💼 事業運営設定',
                'db_table': 'core_business_operation_settings',
            },
        ),
        
        # 👤 ユーザー体験設定モデル追加
        migrations.CreateModel(
            name='UserExperienceSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_support_email', models.EmailField(default='support@biid-user.com', help_text='ユーザー向けサポート連絡先', max_length=254, validators=[django.core.validators.EmailValidator()], verbose_name='ユーザーサポートメール')),
                ('user_support_phone', models.CharField(default='0120-456-789', help_text='ユーザー向けサポート電話番号（フリーダイヤル推奨）', max_length=20, verbose_name='ユーザーサポート電話')),
                ('service_area_description', models.CharField(default='関西域（大阪・京都・神戸）を中心としたプレミアムエリア', help_text='ユーザー向けサービス提供エリアの説明', max_length=200, verbose_name='サービスエリア説明')),
                ('melty_membership_type', models.CharField(choices=[('standard', 'スタンダード会員'), ('premium', 'プレミアム会員'), ('vip', 'VIP会員'), ('platinum', 'プラチナ会員')], default='standard', help_text='デフォルトのMELTY会員レベル', max_length=20, verbose_name='MELTY会員種別')),
                ('biid_initial_rank', models.CharField(choices=[('bronze', 'ブロンズ'), ('silver', 'シルバー'), ('gold', 'ゴールド'), ('platinum', 'プラチナ')], default='bronze', help_text='新規ユーザーの初期ランク', max_length=20, verbose_name='BIID初期ランク')),
                ('welcome_bonus_points', models.IntegerField(default=1000, help_text='新規登録時の付与ポイント', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10000)], verbose_name='ウェルカムボーナスポイント')),
                ('referral_bonus_points', models.IntegerField(default=500, help_text='友達紹介時の付与ポイント', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5000)], verbose_name='紹介ボーナスポイント')),
                ('enable_social_features', models.BooleanField(default=True, help_text='友達機能・投稿・レビューなどのソーシャル機能', verbose_name='ソーシャル機能有効')),
                ('enable_gift_exchange', models.BooleanField(default=True, help_text='ユーザー間でのギフト交換機能', verbose_name='ギフト交換機能')),
                ('enable_point_transfer', models.BooleanField(default=True, help_text='ユーザー間でのポイント送金機能', verbose_name='ポイント送金機能')),
                ('max_daily_point_transfer', models.IntegerField(default=10000, help_text='ユーザーが1日に送金可能な最大ポイント', validators=[django.core.validators.MinValueValidator(100), django.core.validators.MaxValueValidator(100000)], verbose_name='1日最大送金ポイント数')),
                ('default_theme', models.CharField(choices=[('light', 'ライトテーマ'), ('dark', 'ダークテーマ'), ('auto', '自動切り替え')], default='light', help_text='ユーザー画面のデフォルトテーマ', max_length=20, verbose_name='デフォルトテーマ')),
                ('enable_push_notifications', models.BooleanField(default=True, help_text='モバイルアプリでのプッシュ通知機能', verbose_name='プッシュ通知')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '👤 ユーザー体験設定',
                'verbose_name_plural': '👤 ユーザー体験設定',
                'db_table': 'core_user_experience_settings',
            },
        ),
    ]