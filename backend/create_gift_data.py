#!/usr/bin/env python
"""
ギフトテストデータ作成スクリプト
"""
import os
import django
from django.conf import settings

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pointapp.settings')
django.setup()

from core.models import GiftCategory, Gift

def create_gift_data():
    print("ギフトテストデータを作成中...")
    
    # ギフトカテゴリ作成
    categories = [
        {'name': '飲食・グルメ', 'description': 'レストラン・カフェ・お取り寄せ', 'icon': 'utensils'},
        {'name': 'ショッピング', 'description': 'ファッション・雑貨・電化製品', 'icon': 'shopping-bag'},
        {'name': 'エンタメ', 'description': '映画・音楽・ゲーム', 'icon': 'film'},
        {'name': '旅行・体験', 'description': '宿泊・交通・アクティビティ', 'icon': 'plane'},
        {'name': '美容・健康', 'description': '化粧品・サプリ・エステ', 'icon': 'heart'},
    ]
    
    created_categories = []
    for cat_data in categories:
        category, created = GiftCategory.objects.get_or_create(
            name=cat_data['name'],
            defaults={
                'description': cat_data['description'],
                'icon': cat_data['icon']
            }
        )
        if created:
            print(f"✓ カテゴリ作成: {category.name}")
        else:
            print(f"- カテゴリ既存: {category.name}")
        created_categories.append(category)
    
    # ギフト商品作成
    gifts = [
        {
            'name': 'スターバックス ドリンクチケット',
            'description': '全国のスターバックス店舗で使えるドリンクチケット',
            'category': created_categories[0],  # 飲食・グルメ
            'gift_type': 'digital',
            'points_required': 500,
            'original_price': 500,
            'stock_quantity': 1000,
            'unlimited_stock': True,
            'image_url': 'https://example.com/starbucks.jpg',
            'provider_name': 'スターバックス',
            'usage_instructions': 'QRコードをレジで提示してください',
            'terms_conditions': '有効期限: 発行から6ヶ月'
        },
        {
            'name': 'Amazonギフト券 1000円分',
            'description': 'Amazonでのお買い物に使える1000円分のギフト券',
            'category': created_categories[1],  # ショッピング
            'gift_type': 'digital',
            'points_required': 1000,
            'original_price': 1000,
            'stock_quantity': 500,
            'unlimited_stock': False,
            'image_url': 'https://example.com/amazon.jpg',
            'provider_name': 'Amazon',
            'usage_instructions': 'ギフト券番号をAmazonアカウントに登録してください',
            'terms_conditions': '有効期限: 発行から1年'
        },
        {
            'name': 'TOHOシネマズ 映画鑑賞券',
            'description': 'TOHOシネマズで使える映画鑑賞券',
            'category': created_categories[2],  # エンタメ
            'gift_type': 'digital',
            'points_required': 1800,
            'original_price': 1800,
            'stock_quantity': 200,
            'unlimited_stock': False,
            'image_url': 'https://example.com/toho.jpg',
            'provider_name': 'TOHOシネマズ',
            'usage_instructions': 'QRコードを劇場の券売機でスキャンしてください',
            'terms_conditions': '有効期限: 発行から3ヶ月'
        },
        {
            'name': 'JTB旅行券 5000円分',
            'description': 'JTBの旅行商品で使える5000円分の旅行券',
            'category': created_categories[3],  # 旅行・体験
            'gift_type': 'voucher',
            'points_required': 5000,
            'original_price': 5000,
            'stock_quantity': 50,
            'unlimited_stock': False,
            'image_url': 'https://example.com/jtb.jpg',
            'provider_name': 'JTB',
            'usage_instructions': 'JTB店舗または公式サイトでご利用ください',
            'terms_conditions': '有効期限: 発行から1年'
        },
        {
            'name': 'ロクシタン ハンドクリーム',
            'description': '人気のロクシタンハンドクリーム30ml',
            'category': created_categories[4],  # 美容・健康
            'gift_type': 'physical',
            'points_required': 2500,
            'original_price': 2500,
            'stock_quantity': 100,
            'unlimited_stock': False,
            'image_url': 'https://example.com/loccitane.jpg',
            'provider_name': 'ロクシタン',
            'usage_instructions': 'ご指定の住所にお届けします',
            'terms_conditions': '配送まで1-2週間程度'
        },
        {
            'name': 'マクドナルド バリューセット券',
            'description': 'マクドナルドのバリューセット1回分',
            'category': created_categories[0],  # 飲食・グルメ
            'gift_type': 'digital',
            'points_required': 700,
            'original_price': 700,
            'stock_quantity': 2000,
            'unlimited_stock': True,
            'image_url': 'https://example.com/mcdonalds.jpg',
            'provider_name': 'マクドナルド',
            'usage_instructions': 'QRコードをレジで提示してください',
            'terms_conditions': '有効期限: 発行から3ヶ月'
        }
    ]
    
    created_gifts = []
    for gift_data in gifts:
        gift, created = Gift.objects.get_or_create(
            name=gift_data['name'],
            defaults=gift_data
        )
        if created:
            print(f"✓ ギフト作成: {gift.name}")
        else:
            print(f"- ギフト既存: {gift.name}")
        created_gifts.append(gift)
    
    print(f"\n=== ギフトデータ作成完了 ===")
    print(f"カテゴリ: {GiftCategory.objects.count()}件")
    print(f"ギフト商品: {Gift.objects.count()}件")
    
    print("\n=== ギフト一覧 ===")
    for gift in created_gifts:
        print(f"- {gift.name}: {gift.points_required}pt")

if __name__ == "__main__":
    create_gift_data()