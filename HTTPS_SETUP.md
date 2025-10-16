# ローカルHTTPS化手順

Safari でのHTTP→HTTPSリダイレクト問題を解決するため、ローカル開発環境をHTTPS化する手順です。

## 1. mkcertのインストール

```bash
# Homebrewでインストール
brew install mkcert

# ルート証明書をインストール
mkcert -install
```

## 2. 証明書の生成

```bash
cd /Users/youshi/Library/CloudStorage/OneDrive-個人用/claude\ code/melty-pointapp/pointapp-biid

# .certディレクトリを作成
mkdir -p .cert

# localhost用証明書を生成
mkcert -key-file .cert/localhost-key.pem -cert-file .cert/localhost.pem localhost 127.0.0.1
```

## 3. Next.js をHTTPS起動

```bash
# HTTPSでNext.jsを起動
PORT=3000 NODE_OPTIONS="--openssl-legacy-provider" \
npx next dev --hostname localhost --experimental-https \
  --ssl-key .cert/localhost-key.pem --ssl-cert .cert/localhost.pem
```

## 4. アクセスURL

- **HTTPS版**: https://localhost:3000
- **API**: https://localhost:3000/api/health/

## 5. Django設定の調整

backend/pointapp/settings.py に以下を追加:

```python
# HTTPS開発環境用設定
if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'http://localhost:3000',  # フォールバック
    ]
```

## 6. 確認

```bash
curl -k https://localhost:3000/api/health/
```

## 注意事項

- 証明書ファイル（.cert/）は .gitignore に追加してください
- Safari の場合、初回アクセス時に証明書の警告が出る場合があります
- 「詳細設定」→「このWebサイトにアクセス」で進んでください