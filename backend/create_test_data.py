#!/usr/bin/env python
"""
テストデータ作成スクリプト
"""
import os
import django
from django.conf import settings

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pointapp.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Store, PointTransaction
from datetime import datetime, timedelta
import random

User = get_user_model()

def create_test_data():
    print("テストデータを作成中...")
    
    # テストユーザー作成
    test_users = [
        {
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'testpass123',
            'member_id': 'TEST_001',
            'points': 1500,
            'first_name': '太郎',
            'last_name': '田中'
        },
        {
            'username': 'testuser2', 
            'email': 'test2@example.com',
            'password': 'testpass123',
            'member_id': 'TEST_002',
            'points': 2300,
            'first_name': '花子',
            'last_name': '佐藤'
        },
        {
            'username': 'testuser3',
            'email': 'test3@example.com', 
            'password': 'testpass123',
            'member_id': 'TEST_003',
            'points': 800,
            'first_name': '次郎',
            'last_name': '山田'
        }
    ]
    
    created_users = []
    for user_data in test_users:
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'email': user_data['email'],
                'member_id': user_data['member_id'], 
                'points': user_data['points'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name']
            }
        )
        if created:
            user.set_password(user_data['password'])
            user.save()
            print(f"✓ ユーザー作成: {user.username}")
        else:
            print(f"- ユーザー既存: {user.username}")
        created_users.append(user)
    
    # テスト店舗作成
    test_stores = [
        {
            'name': '居酒屋 赤提灯',
            'owner_name': '田中店主',
            'email': 'akachochin@example.com',
            'phone': '06-1234-5678',
            'address': '大阪市北区梅田1-1-1',
            'latitude': 34.702485,
            'longitude': 135.497894,
            'category': 'restaurant',
            'price_range': 'moderate',
            'rating': 4.5,
            'reviews_count': 125
        },
        {
            'name': 'カフェ ブルーマウンテン',
            'owner_name': '山田オーナー',
            'email': 'bluemountain@example.com', 
            'phone': '06-2345-6789',
            'address': '大阪市中央区難波2-2-2',
            'latitude': 34.668285,
            'longitude': 135.502074,
            'category': 'restaurant',
            'price_range': 'budget',
            'rating': 4.2,
            'reviews_count': 89
        },
        {
            'name': 'ドラッグストア健康堂',
            'owner_name': '佐藤店長',
            'email': 'kenkodo@example.com',
            'phone': '06-3456-7890', 
            'address': '大阪市西区本町3-3-3',
            'latitude': 34.685021,
            'longitude': 135.494253,
            'category': 'retail',
            'price_range': 'moderate',
            'rating': 4.0,
            'reviews_count': 67
        }
    ]
    
    created_stores = []
    for store_data in test_stores:
        store, created = Store.objects.get_or_create(
            name=store_data['name'],
            defaults=store_data
        )
        if created:
            print(f"✓ 店舗作成: {store.name}")
        else:
            print(f"- 店舗既存: {store.name}")
        created_stores.append(store)
    
    # テスト取引作成
    print("取引データを作成中...")
    transaction_count = 0
    
    for i in range(20):
        user = random.choice(created_users)
        store = random.choice(created_stores)
        
        # ポイント取引
        if random.choice([True, False]):
            transaction = PointTransaction.objects.create(
                user=user,
                store=store,
                transaction_id=f"TXN-{datetime.now().strftime('%Y%m%d')}-{i+1:03d}",
                amount=random.randint(1000, 5000),
                points_issued=random.randint(100, 500),
                payment_method=random.choice(['cash', 'credit', 'digital']),
                status='completed',
                description=f'{store.name}での購入'
            )
            transaction_count += 1
        
        # チャージ取引
        if random.choice([True, False]):
            transaction = PointTransaction.objects.create(
                user=user,
                store=store,
                transaction_id=f"CHG-{datetime.now().strftime('%Y%m%d')}-{i+1:03d}",
                amount=random.randint(5000, 20000),
                points_issued=0,
                payment_method=random.choice(['credit', 'bank', 'digital']),
                status='completed',
                description='チャージ'
            )
            transaction_count += 1
    
    print(f"✓ 取引作成: {transaction_count}件")
    
    print("\n=== テストデータ作成完了 ===")
    print(f"ユーザー: {User.objects.count()}人")
    print(f"店舗: {Store.objects.count()}店")
    print(f"取引: {PointTransaction.objects.count()}件")
    
    print("\n=== テストアカウント情報 ===")
    print("管理者: admin / admin123")
    print("ユーザー1: testuser1 / testpass123")
    print("ユーザー2: testuser2 / testpass123")
    print("ユーザー3: testuser3 / testpass123")

if __name__ == "__main__":
    create_test_data()