#!/usr/bin/env python
"""
Test data setup script for Gift Exchange API
"""
import os
import sys
import django

# Setup Django environment
if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pointapp.settings')
    django.setup()

from core.models import User, GiftCategory, Gift, Store, PointTransaction, GiftExchange
from django.utils import timezone
from django.contrib.auth.hashers import make_password

def create_test_data():
    print("Setting up test data...")
    
    # Create account ranks
    ranks_data = [
        {
            'name': 'Bronze',
            'points_threshold': 0,
            'daily_send_limit': 500,
            'monthly_send_limit': 5000,
            'send_fee_rate': 0.05,  # 5%
            'max_friends': 50
        },
        {
            'name': 'Silver',
            'points_threshold': 10000,
            'daily_send_limit': 1000,
            'monthly_send_limit': 15000,
            'send_fee_rate': 0.03,  # 3%
            'max_friends': 100
        },
        {
            'name': 'Gold',
            'points_threshold': 50000,
            'daily_send_limit': 2000,
            'monthly_send_limit': 30000,
            'send_fee_rate': 0.01,  # 1%
            'max_friends': 200
        },
        {
            'name': 'Platinum',
            'points_threshold': 100000,
            'daily_send_limit': 5000,
            'monthly_send_limit': 100000,
            'send_fee_rate': 0.0,  # 無料
            'max_friends': 500
        }
    ]
    
    for rank_data in ranks_data:
        rank, created = AccountRank.objects.get_or_create(
            name=rank_data['name'],
            defaults=rank_data
        )
        if created:
            print(f"✓ Account rank created: {rank_data['name']}")
    
    # Create a default store if it doesn't exist
    store, created = Store.objects.get_or_create(
        name='デフォルト店舗',
        defaults={
            'address': '東京都渋谷区',
            'phone': '03-1234-5678',
            'email': 'store@example.com'
        }
    )
    if created:
        print("✓ Default store created")
    
    # Create test users
    test_users_data = [
        {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123',
            'points': 50000,
            'member_id': 'TEST001'
        },
        {
            'username': 'alice',
            'email': 'alice@example.com',
            'first_name': 'Alice',
            'last_name': 'Smith',
            'password': 'alice123',
            'points': 25000,
            'member_id': 'TEST002'
        },
        {
            'username': 'bob',
            'email': 'bob@example.com',
            'first_name': 'Bob',
            'last_name': 'Johnson',
            'password': 'bob123',
            'points': 75000,
            'member_id': 'TEST003'
        }
    ]
    
    for user_data in test_users_data:
        test_user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'email': user_data['email'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'password': make_password(user_data['password']),
                'points': user_data['points'],
                'member_id': user_data['member_id'],
                'status': 'active',
                'registration_date': timezone.now(),
                'last_login_date': timezone.now()
            }
        )
        if created:
            print(f"✓ Test user created: {user_data['username']} (password: {user_data['password']})")
        else:
            print(f"✓ Test user already exists: {user_data['username']}")
        
        # ランクを自動設定
        test_user.get_current_rank()
    
    # Create gift categories
    categories_data = [
        {'name': 'グルメ・食品', 'icon': '🍽️', 'color': 'from-orange-400 to-red-500'},
        {'name': 'ファッション', 'icon': '👗', 'color': 'from-purple-400 to-pink-500'},
        {'name': 'デジタル', 'icon': '💻', 'color': 'from-blue-400 to-cyan-500'},
        {'name': '美容・健康', 'icon': '💄', 'color': 'from-pink-400 to-rose-500'},
        {'name': 'エンタメ', 'icon': '🎬', 'color': 'from-indigo-400 to-purple-500'},
        {'name': 'ライフスタイル', 'icon': '🏠', 'color': 'from-green-400 to-emerald-500'}
    ]
    
    for cat_data in categories_data:
        category, created = GiftCategory.objects.get_or_create(
            name=cat_data['name'],
            defaults={
                'description': f'{cat_data["name"]}カテゴリのギフト商品',
                'is_active': True
            }
        )
        if created:
            print(f"✓ Category created: {cat_data['name']}")
    
    # Create test gifts
    gifts_data = [
        {
            'name': 'スターバックス ギフトカード 3,000円分',
            'description': '全国のスターバックスで利用可能なデジタルギフトカードです。',
            'category_name': 'グルメ・食品',
            'gift_type': 'digital',
            'points_required': 2800,
            'original_price': 3000,
            'provider_name': 'スターバックス',
            'unlimited_stock': True,
            'status': 'active'
        },
        {
            'name': 'Amazonギフトカード 5,000円分',
            'description': 'Amazonでのお買い物に使えるデジタルギフトカードです。',
            'category_name': 'デジタル',
            'gift_type': 'digital',
            'points_required': 4500,
            'original_price': 5000,
            'provider_name': 'Amazon',
            'unlimited_stock': True,
            'status': 'active'
        },
        {
            'name': 'ユニクロ 商品券 2,000円分',
            'description': 'ユニクロ全店舗で利用可能な商品券です。',
            'category_name': 'ファッション',
            'gift_type': 'voucher',
            'points_required': 1900,
            'original_price': 2000,
            'provider_name': 'ユニクロ',
            'unlimited_stock': False,
            'stock_quantity': 25,
            'status': 'active'
        },
        {
            'name': 'ロクシタン ハンドクリームセット',
            'description': '人気のハンドクリーム3本セットです。ギフトボックス付き。',
            'category_name': '美容・健康',
            'gift_type': 'physical',
            'points_required': 3200,
            'original_price': 4500,
            'provider_name': 'ロクシタン',
            'unlimited_stock': False,
            'stock_quantity': 12,
            'status': 'active'
        },
        {
            'name': 'Netflix 1ヶ月無料券',
            'description': 'Netflix プレミアムプランを1ヶ月間無料でお楽しみいただけます。',
            'category_name': 'エンタメ',
            'gift_type': 'digital',
            'points_required': 1200,
            'original_price': 1980,
            'provider_name': 'Netflix',
            'unlimited_stock': True,
            'status': 'active'
        }
    ]
    
    for gift_data in gifts_data:
        category = GiftCategory.objects.get(name=gift_data['category_name'])
        gift, created = Gift.objects.get_or_create(
            name=gift_data['name'],
            defaults={
                'description': gift_data['description'],
                'category': category,
                'gift_type': gift_data['gift_type'],
                'points_required': gift_data['points_required'],
                'original_price': gift_data['original_price'],
                'provider_name': gift_data['provider_name'],
                'unlimited_stock': gift_data['unlimited_stock'],
                'stock_quantity': gift_data.get('stock_quantity', 0),
                'status': gift_data['status'],
                'image_url': '',
                'terms_conditions': 'ご利用前に提供元の利用規約をご確認ください。',
                'exchange_count': 0
            }
        )
        if created:
            print(f"✓ Gift created: {gift_data['name']}")
    
    print("\n🎉 Test data setup completed!")
    print(f"📊 Summary:")
    print(f"   - Account Ranks: {AccountRank.objects.count()}")
    print(f"   - Test Users: {User.objects.count()}")
    print(f"   - Categories: {GiftCategory.objects.count()}")
    print(f"   - Gifts: {Gift.objects.count()}")
    print(f"\n👥 Test Users:")
    print(f"   - testuser (50,000pt) - Gold rank")
    print(f"   - alice (25,000pt) - Silver rank") 
    print(f"   - bob (75,000pt) - Gold rank")
    print(f"\n🏆 Account Ranks:")
    for rank in AccountRank.objects.all():
        print(f"   - {rank.name}: ≥{rank.points_threshold}pt (daily: {rank.daily_send_limit}pt, fee: {rank.send_fee_rate*100}%)")
    print(f"\n🌐 Backend running at: http://localhost:8000")
    print(f"🎨 Frontend running at: http://localhost:3000")

if __name__ == "__main__":
    create_test_data()