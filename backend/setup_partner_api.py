import os
import django
import sys

# Django設定
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pointapp.settings')
django.setup()

from core.models import Brand, APIAccessKey
from core.partner_auth import generate_totp_secret, generate_access_key

def setup_brands():
    """ブランドの初期データを作成"""
    brands_data = [
        {
            'code': 'amazon',
            'name': 'Amazon',
            'description': 'Amazon ギフト券',
            'allowed_prices': [100, 500, 1000, 3000, 5000, 10000]
        },
        {
            'code': 'paypay',
            'name': 'PayPay',
            'description': 'PayPay ギフト',
            'allowed_prices': [100, 500, 1000, 3000, 5000, 10000]
        },
        {
            'code': 'itunes',
            'name': 'iTunes',
            'description': 'iTunes ギフト',
            'allowed_prices': [500, 1000, 3000, 5000, 10000]
        },
        {
            'code': 'googleplay',
            'name': 'Google Play',
            'description': 'Google Play ギフト',
            'allowed_prices': [500, 1000, 3000, 5000, 10000]
        },
        {
            'code': 'steam',
            'name': 'Steam',
            'description': 'Steam ギフト',
            'allowed_prices': [1000, 3000, 5000, 10000]
        },
        {
            'code': 'nintendo',
            'name': 'Nintendo',
            'description': 'Nintendo ギフト',
            'allowed_prices': [1000, 3000, 5000, 10000]
        },
        {
            'code': 'starbucks',
            'name': 'Starbucks',
            'description': 'Starbucks ギフト',
            'allowed_prices': [500, 1000, 3000, 5000]
        },
        {
            'code': 'LINE',
            'name': 'LINE',
            'description': 'LINEギフト',
            'allowed_prices': [100, 500, 1000, 3000, 5000]
        }
    ]
    
    created_count = 0
    for brand_data in brands_data:
        brand, created = Brand.objects.get_or_create(
            code=brand_data['code'],
            defaults={
                'name': brand_data['name'],
                'description': brand_data['description'],
                'allowed_prices': brand_data['allowed_prices'],
                'is_active': True
            }
        )
        if created:
            created_count += 1
            print(f"Created brand: {brand.name}")
    
    print(f"Brand setup completed. Created {created_count} new brands.")
    print(f"Total brands: {Brand.objects.count()}")

def setup_demo_api_key():
    """デモ用APIキーを作成"""
    partner_name = "Demo Partner"
    
    # 既存のキーをチェック
    if APIAccessKey.objects.filter(partner_name=partner_name).exists():
        print(f"API key for {partner_name} already exists.")
        return
    
    # 新しいAPIキーを生成
    access_key = generate_access_key()
    shared_secret = generate_totp_secret()
    
    api_key = APIAccessKey.objects.create(
        key=access_key,
        partner_name=partner_name,
        shared_secret=shared_secret,
        hash_algorithm='SHA1',
        time_step=30,
        totp_digits=6,
        is_active=True
    )
    
    print(f"Created API key for {partner_name}")
    print(f"Access Key: {access_key}")
    print(f"Shared Secret: {shared_secret}")
    print(f"Hash Algorithm: SHA1")
    print(f"Time Step: 30 seconds")
    print(f"TOTP Digits: 6")
    print("\nIMPORTANT: Store these values securely!")

def main():
    """メイン処理"""
    print("Setting up Partner API data...")
    print("=" * 50)
    
    # ブランドの初期データを作成
    setup_brands()
    print()
    
    # デモ用APIキーを作成
    setup_demo_api_key()
    print()
    
    print("=" * 50)
    print("Partner API setup completed successfully!")
    print("\nTo test the API, use the following headers:")
    print("x-realpay-gift-api-access-key: [Access Key from above]")
    print("x-realpay-gift-api-access-token: [TOTP generated from shared secret]")
    print("x-realpay-gift-api-request-id: [Unique request ID for POST/PUT/DELETE]")

if __name__ == "__main__":
    main()