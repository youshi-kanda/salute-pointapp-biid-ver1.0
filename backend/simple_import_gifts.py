#!/usr/bin/env python
"""
Simple demo gift data import script for biid point system
"""
import os
import sys
import django
import csv
from datetime import datetime

# Setup Django environment
if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pointapp.settings')
    django.setup()

from core.models import GiftCategory, Gift, GiftExchange, User
from django.utils import timezone

def import_demo_gifts():
    """デモギフトデータをインポート"""
    print("Starting demo gift import...")
    
    # CSVファイルパス
    csv_file_path = r"C:\Users\rockr\OneDrive\claude code\melty-pointapp\API関連\デモギフト_biid株式会社様.csv"
    
    if not os.path.exists(csv_file_path):
        print(f"CSV file not found: {csv_file_path}")
        return
    
    # 既存データをクリア
    Gift.objects.all().delete()
    GiftCategory.objects.all().delete()
    
    # ギフトカテゴリを作成
    print("Creating gift categories...")
    demo_category = GiftCategory.objects.create(
        name='biid Demo Gifts',
        description='Demo gifts for biid corporation',
        icon='demo-gift',
        is_active=True
    )
    
    # CSVファイルを読み込み
    print("Reading CSV file...")
    gifts_data = []
    
    try:
        with open(csv_file_path, 'r', encoding='shift_jis') as file:
            reader = csv.reader(file)
            headers = next(reader)  # ヘッダーをスキップ
            
            for i, row in enumerate(reader):
                if len(row) >= 9 and row[1]:  # 必要なデータがあるかチェック
                    gift_data = {
                        'category_name': row[0],
                        'gift_name': row[1],
                        'amount': row[2],
                        'gift_url': row[3],
                        'expiry_date': row[4],
                        'user_address': row[5],
                        'delivery_name': row[6],
                        'quantity': row[7],
                        'management_code': row[8]
                    }
                    gifts_data.append(gift_data)
    
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    print(f"Found {len(gifts_data)} gift records")
    
    # ギフトデータを登録
    print("Registering gifts...")
    imported_count = 0
    
    for i, gift_data in enumerate(gifts_data):
        try:
            # 金額を解析
            amount = 5000  # デフォルト値
            try:
                amount = int(float(gift_data['amount']))
            except (ValueError, TypeError):
                pass
            
            # 有効期限を解析
            expires_at = None
            try:
                if gift_data['expiry_date']:
                    expires_at = datetime.strptime(gift_data['expiry_date'], '%Y/%m/%d %H:%M')
                    expires_at = timezone.make_aware(expires_at)
            except (ValueError, TypeError):
                pass
            
            # ギフトを作成
            gift = Gift.objects.create(
                name=f"Demo Gift {i+1} ({amount} yen)",
                description=f"Demo gift for biid corporation - {amount} yen value",
                category=demo_category,
                gift_type='digital',
                points_required=amount,
                original_price=amount,
                unlimited_stock=False,
                stock_quantity=1,
                provider_name='biid Corporation',
                provider_url='https://demo.digital-gift.jp/',
                image_url='https://demo.digital-gift.jp/images/demo-gift.jpg',
                status='active',
                available_until=expires_at,
                usage_instructions='Demo gift - not for actual use',
                terms_conditions='Demo purposes only'
            )
            
            # 管理者ユーザーを取得
            admin_user = User.objects.filter(role='admin').first()
            if admin_user:
                # 未使用のギフトコードとして保存
                GiftExchange.objects.create(
                    user=admin_user,
                    gift=gift,
                    points_spent=0,
                    exchange_code=gift_data['management_code'],
                    status='pending',
                    digital_url=gift_data['gift_url'],
                    notes=f"Demo unused code - Management code: {gift_data['management_code']}"
                )
            
            imported_count += 1
            print(f"Registered gift {i+1}: {gift.name}")
            
        except Exception as e:
            print(f"Error registering gift {i+1}: {e}")
            continue
    
    print(f"\nImport completed!")
    print(f"Total gifts imported: {imported_count}")
    print(f"Gift categories created: 1")
    print("System is ready for gift exchange testing!")

if __name__ == "__main__":
    import_demo_gifts()