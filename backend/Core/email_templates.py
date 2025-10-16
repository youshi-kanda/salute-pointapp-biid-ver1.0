"""
メールテンプレートの定義
"""

EMAIL_TEMPLATES = {
    'store_registration_admin': {
        'name': 'store_registration_admin',
        'subject': '[biid Store] 新店舗登録: {{ store_name }}',
        'description': '管理者向け店舗登録通知メール',
        'available_variables': [
            'store_name', 'store_owner', 'store_email', 'store_phone', 
            'store_address', 'area_name', 'registration_date', 'admin_url'
        ],
        'body_html': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>新店舗登録通知</title>
    <style>
        body { font-family: 'Hiragino Sans', 'Noto Sans JP', Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #ec4899 0%, #f43f5e 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #fff; padding: 30px; border: 1px solid #e5e7eb; }
        .store-info { background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .button { display: inline-block; background: #ec4899; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 10px 0; }
        .footer { background: #f3f4f6; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-radius: 0 0 8px 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏪 新店舗登録通知</h1>
        </div>
        
        <div class="content">
            <p>管理者様</p>
            
            <p>新しい店舗が登録されました。承認をお願いいたします。</p>
            
            <div class="store-info">
                <h3>📋 店舗情報</h3>
                <p><strong>店舗名:</strong> {{ store_name }}</p>
                <p><strong>店舗オーナー:</strong> {{ store_owner }}</p>
                <p><strong>メールアドレス:</strong> {{ store_email }}</p>
                <p><strong>電話番号:</strong> {{ store_phone }}</p>
                <p><strong>住所:</strong> {{ store_address }}</p>
                <p><strong>エリア:</strong> {{ area_name }}</p>
                <p><strong>登録日時:</strong> {{ registration_date }}</p>
            </div>
            
            <p>以下のリンクから管理画面で詳細を確認し、承認・却下の処理を行ってください。</p>
            
            <a href="{{ admin_url }}" class="button">管理画面で確認</a>
        </div>
        
        <div class="footer">
            <p>biid Store 管理システム</p>
            <p>このメールは自動送信されています。</p>
        </div>
    </div>
</body>
</html>
        ''',
        'body_text': '''
新店舗登録通知

管理者様

新しい店舗が登録されました。承認をお願いいたします。

【店舗情報】
店舗名: {{ store_name }}
店舗オーナー: {{ store_owner }}
メールアドレス: {{ store_email }}
電話番号: {{ store_phone }}
住所: {{ store_address }}
エリア: {{ area_name }}
登録日時: {{ registration_date }}

管理画面URL: {{ admin_url }}

biid Store 管理システム
        '''
    },
    
    'store_welcome': {
        'name': 'store_welcome',
        'subject': '[biid Store] 店舗登録ありがとうございます - {{ store_name }}',
        'description': '店舗登録完了ウェルカムメール',
        'available_variables': [
            'store_name', 'owner_name', 'area_name', 'login_url', 'support_email'
        ],
        'body_html': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>店舗登録完了</title>
    <style>
        body { font-family: 'Hiragino Sans', 'Noto Sans JP', Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #ec4899 0%, #f43f5e 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #fff; padding: 30px; border: 1px solid #e5e7eb; }
        .welcome-box { background: #fdf2f8; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ec4899; }
        .button { display: inline-block; background: #ec4899; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 10px 0; }
        .footer { background: #f3f4f6; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-radius: 0 0 8px 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 店舗登録完了</h1>
        </div>
        
        <div class="content">
            <p>{{ owner_name }} 様</p>
            
            <div class="welcome-box">
                <h3>「{{ store_name }}」の登録ありがとうございます！</h3>
                <p>{{ area_name }}エリアでの店舗登録が完了いたしました。</p>
            </div>
            
            <h3>📋 次のステップ</h3>
            <ol>
                <li><strong>承認をお待ちください</strong><br>
                   運営チームが店舗情報を確認し、承認処理を行います（通常1-2営業日）。</li>
                <li><strong>承認完了後</strong><br>
                   サービスをご利用いただけるようになります。</li>
                <li><strong>ログイン準備</strong><br>
                   承認完了後、店舗管理画面にログインできます。</li>
            </ol>
            
            <p>承認完了後は以下のURLから管理画面にアクセスできます：</p>
            <a href="{{ login_url }}" class="button">店舗管理画面</a>
            
            <h3>📞 サポート</h3>
            <p>ご不明点がございましたら、お気軽にお問い合わせください。</p>
            <p>サポートメール: <a href="mailto:{{ support_email }}">{{ support_email }}</a></p>
        </div>
        
        <div class="footer">
            <p>biid Store</p>
            <p>このメールは自動送信されています。</p>
        </div>
    </div>
</body>
</html>
        ''',
        'body_text': '''
店舗登録完了

{{ owner_name }} 様

「{{ store_name }}」の登録ありがとうございます！
{{ area_name }}エリアでの店舗登録が完了いたしました。

【次のステップ】
1. 承認をお待ちください
   運営チームが店舗情報を確認し、承認処理を行います（通常1-2営業日）。

2. 承認完了後
   サービスをご利用いただけるようになります。

3. ログイン準備
   承認完了後、店舗管理画面にログインできます。

店舗管理画面URL: {{ login_url }}

【サポート】
ご不明点がございましたら、お気軽にお問い合わせください。
サポートメール: {{ support_email }}

biid Store
        '''
    },
    
    'store_approval': {
        'name': 'store_approval',
        'subject': '[biid Store] 店舗登録が承認されました - {{ store_name }}',
        'description': '店舗承認通知メール',
        'available_variables': [
            'store_name', 'owner_name', 'approval_date', 'login_url', 'getting_started_url'
        ],
        'body_html': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>店舗承認完了</title>
    <style>
        body { font-family: 'Hiragino Sans', 'Noto Sans JP', Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #fff; padding: 30px; border: 1px solid #e5e7eb; }
        .approval-box { background: #f0fdf4; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10b981; }
        .button { display: inline-block; background: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 10px 5px; }
        .button-secondary { background: #6b7280; }
        .footer { background: #f3f4f6; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; border-radius: 0 0 8px 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ 店舗承認完了</h1>
        </div>
        
        <div class="content">
            <p>{{ owner_name }} 様</p>
            
            <div class="approval-box">
                <h3>おめでとうございます！「{{ store_name }}」が承認されました</h3>
                <p>{{ approval_date }}に承認が完了し、biid Storeサービスをご利用いただけるようになりました。</p>
            </div>
            
            <h3>🚀 今すぐ始められること</h3>
            <ul>
                <li><strong>店舗管理画面にログイン</strong> - 基本設定やプロフィール編集</li>
                <li><strong>ポイント設定</strong> - 顧客に付与するポイント率の設定</li>
                <li><strong>プロモーション作成</strong> - 集客のための特別キャンペーン</li>
                <li><strong>売上・分析確認</strong> - リアルタイムの売上データをチェック</li>
            </ul>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ login_url }}" class="button">店舗管理画面にログイン</a>
                <a href="{{ getting_started_url }}" class="button button-secondary">スタートガイド</a>
            </div>
            
            <h3>💡 サポート情報</h3>
            <p>店舗運営に関するご質問やサポートが必要でしたら、いつでもお気軽にお問い合わせください。</p>
            <p>成功する店舗運営をbiid Storeがサポートします！</p>
        </div>
        
        <div class="footer">
            <p>biid Store</p>
            <p>素晴らしいスタートを切りましょう！</p>
        </div>
    </div>
</body>
</html>
        ''',
        'body_text': '''
店舗承認完了

{{ owner_name }} 様

おめでとうございます！「{{ store_name }}」が承認されました

{{ approval_date }}に承認が完了し、biid Storeサービスをご利用いただけるようになりました。

【今すぐ始められること】
- 店舗管理画面にログイン - 基本設定やプロフィール編集
- ポイント設定 - 顧客に付与するポイント率の設定
- プロモーション作成 - 集客のための特別キャンペーン
- 売上・分析確認 - リアルタイムの売上データをチェック

店舗管理画面: {{ login_url }}
スタートガイド: {{ getting_started_url }}

【サポート情報】
店舗運営に関するご質問やサポートが必要でしたら、いつでもお気軽にお問い合わせください。
成功する店舗運営をbiid Storeがサポートします！

biid Store
        '''
    }
}