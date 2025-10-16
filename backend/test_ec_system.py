#!/usr/bin/env python
"""
EC購入ポイント付与システムの統合テスト
各機能の連携を確認するテストスクリプト
"""

import os
import django
import sys
from decimal import Decimal
from datetime import datetime, timedelta

# Django設定
sys.path.append('/Users/youshi/Desktop/projects/biid/melty-pointapp/biid-pointapp-salute/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pointapp.settings')
django.setup()

from core.models import User, Store, ECPointRequest, StoreWebhookKey
from core.duplicate_detection_service import DuplicateDetectionService
from core.ec_payment_service import ec_payment_service
from django.utils import timezone


def test_duplicate_detection():
    """重複検知サービスのテスト"""
    print("=== 重複検知テスト ===")
    
    try:
        # テスト用データ作成
        user = User.objects.filter(role='customer').first()
        store = Store.objects.filter(status='active').first()
        
        if not user or not store:
            print("❌ テスト用のユーザーまたは店舗が見つかりません")
            return False
        
        # 重複検知サービス
        detector = DuplicateDetectionService()
        
        # 1. 通常の申請
        duplicates = detector.check_for_duplicates(
            user=user,
            store=store,
            amount=Decimal('5000.00'),
            order_id='test_order_123',
            purchase_date=timezone.now()
        )
        
        print(f"✅ 重複検知実行完了: {len(duplicates)}件の潜在的重複を検知")
        
        # 2. 統計情報取得
        stats = detector.get_duplicate_statistics(days=30)
        print(f"✅ 重複検知統計: 総検知数 {stats['total_detections']}件")
        
        return True
        
    except Exception as e:
        print(f"❌ 重複検知テスト失敗: {str(e)}")
        return False


def test_payment_service():
    """決済サービスのテスト"""
    print("\n=== 決済サービステスト ===")
    
    try:
        store = Store.objects.filter(status='active').first()
        if not store:
            print("❌ テスト用の店舗が見つかりません")
            return False
        
        # 1. 決済状況ヘルスチェック
        health = ec_payment_service.check_store_payment_health(store)
        
        if health['success']:
            print(f"✅ 決済ヘルスチェック完了: {health['health']['overall']}")
            print(f"   残高: {health['current_balance']}円")
            if health['health']['issues']:
                print(f"   課題: {', '.join(health['health']['issues'])}")
        else:
            print(f"❌ ヘルスチェック失敗: {health['error']}")
        
        # 2. 決済履歴取得
        history = ec_payment_service.get_payment_history(store, days=7)
        
        if history['success']:
            print(f"✅ 決済履歴取得完了: 過去7日間")
            print(f"   ECリクエスト: {history['stats']['ec_requests']['total']}件")
            print(f"   デポジット取引: {history['stats']['deposit_consumption']['total_transactions']}件")
        else:
            print(f"❌ 決済履歴取得失敗: {history['error']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 決済サービステスト失敗: {str(e)}")
        return False


def test_webhook_key_generation():
    """Webhookキー生成テスト"""
    print("\n=== Webhookキー生成テスト ===")
    
    try:
        # ランダムキー生成
        key1 = StoreWebhookKey.generate_key()
        key2 = StoreWebhookKey.generate_key()
        
        # 異なるキーが生成されることを確認
        assert key1 != key2, "同じキーが生成されました"
        assert len(key1) == 64, f"キー長が不正です: {len(key1)}"
        
        print(f"✅ Webhookキー生成成功")
        print(f"   キー1: {key1[:16]}...")
        print(f"   キー2: {key2[:16]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Webhookキー生成テスト失敗: {str(e)}")
        return False


def test_ec_request_methods():
    """ECPointRequestモデルのメソッドテスト"""
    print("\n=== ECPointRequestメソッドテスト ===")
    
    try:
        # テスト用データ
        user = User.objects.filter(role='customer').first()
        store = Store.objects.filter(status='active').first()
        
        if not user or not store:
            print("❌ テスト用データが見つかりません")
            return False
        
        # 1. ポイント計算テスト
        test_amounts = [Decimal('100'), Decimal('1500'), Decimal('9999')]
        
        for amount in test_amounts:
            # 仮のECPointRequestオブジェクト
            request = ECPointRequest(purchase_amount=amount)
            points = request.calculate_points()
            expected = int(amount // 100)
            
            assert points == expected, f"ポイント計算エラー: {amount}円 → {points}pt (期待値: {expected}pt)"
            print(f"✅ ポイント計算: {amount}円 → {points}pt")
        
        # 2. ハッシュ生成テスト
        request = ECPointRequest(
            user_id=user.id,
            store_id=store.id,
            order_id='test_123',
            purchase_amount=Decimal('5000'),
            purchase_date=timezone.now()
        )
        
        hash1 = request.generate_request_hash()
        hash2 = request.generate_request_hash()
        
        assert hash1 == hash2, "同じデータから異なるハッシュが生成されました"
        assert len(hash1) == 64, f"ハッシュ長が不正です: {len(hash1)}"
        
        print(f"✅ ハッシュ生成: {hash1[:16]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ ECPointRequestメソッドテスト失敗: {str(e)}")
        return False


def test_data_integrity():
    """データ整合性テスト"""
    print("\n=== データ整合性テスト ===")
    
    try:
        # 1. 必要なテーブルの存在確認
        tables_check = [
            (User, "User"),
            (Store, "Store"),
            (ECPointRequest, "ECPointRequest"),
            (StoreWebhookKey, "StoreWebhookKey")
        ]
        
        for model, name in tables_check:
            try:
                count = model.objects.count()
                print(f"✅ {name}テーブル: {count}レコード")
            except Exception as e:
                print(f"❌ {name}テーブルエラー: {str(e)}")
                return False
        
        # 2. 関係性チェック
        active_stores = Store.objects.filter(status='active').count()
        customers = User.objects.filter(role='customer').count()
        
        print(f"✅ アクティブ店舗: {active_stores}件")
        print(f"✅ 顧客ユーザー: {customers}件")
        
        if active_stores == 0:
            print("⚠️  テスト用のアクティブ店舗がありません")
        
        if customers == 0:
            print("⚠️  テスト用の顧客がいません")
        
        return True
        
    except Exception as e:
        print(f"❌ データ整合性テスト失敗: {str(e)}")
        return False


def main():
    """メインテスト実行"""
    print("EC購入ポイント付与システム 統合テスト開始")
    print("=" * 50)
    
    tests = [
        test_data_integrity,
        test_webhook_key_generation,
        test_ec_request_methods,
        test_duplicate_detection,
        test_payment_service
    ]
    
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ テスト実行エラー: {str(e)}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("テスト結果サマリー")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"成功: {passed}/{total} テスト")
    
    if passed == total:
        print("🎉 全テストが成功しました！")
        print("EC購入ポイント付与システムは正常に動作する準備ができています。")
    else:
        print("⚠️  一部テストが失敗しました。")
        print("実際のデータベースマイグレーション実行後に再テストを推奨します。")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)