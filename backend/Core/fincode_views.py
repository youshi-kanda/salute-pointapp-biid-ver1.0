# GMO FINCODE 決済 API ビュー

from django.conf import settings
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
import json
import time
import random
import string
import logging
from typing import Dict, Any
from .fincode_service import fincode_service, FINCODEError
from .models import User, PaymentTransaction
from .serializers import PaymentTransactionSerializer

logger = logging.getLogger(__name__)


class FincodeApiError(Exception):
    pass


def _uniq_order_id(prefix="ORD"):
    """ユニークなOrderIDを生成"""
    nonce = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefix}_{int(time.time())}_{nonce}"


@csrf_exempt
@require_POST
def initiate_payment(request):
    """
    決済開始。入力検証→（モック or 実呼び出し）→結果を透過返却。
    """
    try:
        body = json.loads(request.body.decode())
        amount = int(body.get("amount", 0))
        order_id = body.get("order_id") or _uniq_order_id()
        payment_method = (body.get("payment_method") or "card").lower()
        customer_id = body.get("customer_id", "")

        logger.info(f"🔄 FINCODE payment initiation: order_id={order_id}, amount={amount}, method={payment_method}, customer_id={customer_id}")

        # 入力検証
        if amount <= 0:
            logger.warning(f"❌ Invalid amount: {amount}")
            return JsonResponse({"success": False, "error": "INVALID_AMOUNT", "detail": f"金額が無効です: {amount}"}, status=400)
        
        if not order_id:
            logger.warning("❌ Missing order_id")
            return JsonResponse({"success": False, "error": "MISSING_ORDER_ID", "detail": "注文IDが必要です"}, status=400)

        if not customer_id:
            logger.warning("❌ Missing customer_id")
            return JsonResponse({"success": False, "error": "MISSING_CUSTOMER_ID", "detail": "顧客IDが必要です"}, status=400)

        # モック動作：開発を止めないため
        if getattr(settings, "FINCODE_MOCK", False):
            logger.info(f"🎭 Mock mode: returning success for order_id={order_id}")
            # ローカルモック決済ページURL
            base_url = request.build_absolute_uri('/').rstrip('/')
            mock_response = {
                "id": f"MOCK_{int(time.time())}_{random.randint(1000, 9999)}",
                "order_id": order_id,
                "amount": amount,
                "status": "UNPROCESSED",
                "pay_type": payment_method,
                "redirect_url": f"{base_url}/api/fincode/mock-payment/{order_id}/?method={payment_method}&amount={amount}",
                "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "updated": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            return JsonResponse({
                "success": True,
                "mock": True,
                "fincode": mock_response,
                "payment_id": mock_response["id"],
                "redirect_url": mock_response["redirect_url"],
                "order_id": order_id,
                "status": "pending"
            }, status=200)

        # ---- 本番呼び出し ----
        try:
            logger.info(f"🔄 Calling FINCODE service: order_id={order_id}, amount={amount}")
            
            # FINCODE サービス呼び出し
            payment_data = {
                'order_id': order_id,
                'amount': amount,
                'currency': 'JPY',
                'customer_id': customer_id,
                'customer_name': body.get('customer_name', ''),
                'customer_email': body.get('customer_email', ''),
                'payment_method': payment_method,
                'description': f'BIID Point App Payment - {payment_method}',
                'return_url': f"{request.build_absolute_uri('/').rstrip('/')}/api/fincode/payment/return/{order_id}/",
                'cancel_url': f"{request.build_absolute_uri('/').rstrip('/')}/api/fincode/payment/cancel/{order_id}/",
                'notify_url': f"{request.build_absolute_uri('/').rstrip('/')}/api/fincode/payment/notify/",
                'metadata': {
                    'original_amount': amount,
                    'payment_method': payment_method,
                    'terminal_id': body.get('terminal_id', 'TERMINAL_001'),
                    'store_id': body.get('store_id', '')
                }
            }
            
            exec_result = fincode_service.initiate_payment(payment_data)
            logger.info(f"✅ FINCODE service response: {exec_result}")
            
        except FINCODEError as e:
            logger.error(f"❌ FINCODE service error: {str(e)}")
            return JsonResponse({
                "success": False, 
                "error": "FINCODE_API_ERROR",
                "detail": str(e),
                "error_code": e.error_code
            }, status=422)
        except Exception as e:
            logger.error(f"❌ FINCODE service error: {str(e)}")
            raise FincodeApiError(f"FINCODE service error: {str(e)}")
        
        # 戻り値検証
        if not isinstance(exec_result, dict):
            logger.error(f"❌ FINCODE returned non-dict response: {type(exec_result)}")
            raise FincodeApiError("fincode service returned non-dict response")

        # エラーチェック
        if not exec_result.get("success", False):
            logger.warning(f"🚨 FINCODE payment failed: {exec_result}")
            return JsonResponse({
                "success": False, 
                "fincode": exec_result,
                "error": exec_result.get("error", "Payment initiation failed")
            }, status=422)

        logger.info(f"✅ Payment initiation successful: {exec_result}")
        return JsonResponse({
            "success": True, 
            "fincode": exec_result,
            "payment_id": exec_result.get('payment_id'),
            "redirect_url": exec_result.get('redirect_url'),
            "order_id": order_id,
            "status": exec_result.get('status', 'pending'),
            "db_transaction_id": exec_result.get('db_transaction_id')
        }, status=200)

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {str(e)}")
        return JsonResponse({"success": False, "error": "INVALID_JSON", "detail": "無効なJSONデータです"}, status=400)
    
    except ValueError as e:
        logger.error(f"❌ Value error: {str(e)}")
        return JsonResponse({"success": False, "error": "INVALID_DATA", "detail": str(e)}, status=400)
    
    except FincodeApiError as e:
        logger.error(f"❌ FINCODE API error: {str(e)}")
        return JsonResponse({"success": False, "error": "FINCODE_API_ERROR", "detail": str(e)}, status=502)
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return JsonResponse({"success": False, "error": "SERVER_EXCEPTION", "detail": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def check_payment_status(request, payment_id):
    """決済状態確認API"""
    try:
        logger.info(f"🔍 Checking payment status: {payment_id}")
        
        if getattr(settings, "FINCODE_MOCK", False):
            # モック: ランダムで状態を返す
            statuses = ["pending", "processing", "completed", "failed"]
            mock_status = random.choice(statuses)
            return JsonResponse({
                "success": True,
                "mock": True,
                "status": mock_status,
                "payment_id": payment_id,
                "order_id": f"ORDER_{int(time.time())}",
                "amount": 30000,
                "payment_method": "card",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
            })
        
        # 実装: FINCODE APIで状態確認
        result = fincode_service.check_payment_status(payment_id)
        
        if result.get('success', False):
            return JsonResponse({
                "success": True, 
                "fincode": result,
                "status": result.get("status"),
                "payment_id": payment_id,
                "order_id": result.get("order_id"),
                "amount": result.get("amount"),
                "payment_method": result.get("payment_method"),
                "completed_at": result.get("completed_at"),
                "updated_at": result.get("updated_at")
            })
        else:
            return JsonResponse({
                "success": False,
                "error": "STATUS_CHECK_FAILED",
                "detail": result.get("error_message", "Status check failed")
            }, status=500)
    
    except Exception as e:
        logger.error(f"❌ Status check error: {str(e)}")
        return JsonResponse({"success": False, "error": "STATUS_CHECK_ERROR", "detail": str(e)}, status=500)


@csrf_exempt
@require_POST
def refund_payment(request, payment_id):
    """返金処理API"""
    try:
        body = json.loads(request.body.decode()) if request.body else {}
        amount = body.get("amount")  # 部分返金の場合
        reason = body.get("reason", "")
        
        logger.info(f"💸 FINCODE refund request: payment_id={payment_id}, amount={amount}")
        
        if getattr(settings, "FINCODE_MOCK", False):
            # モック返金
            return JsonResponse({
                "success": True,
                "mock": True,
                "refund_id": f"REFUND_MOCK_{int(time.time())}",
                "refund_amount": amount or 30000,
                "status": "completed"
            })
        
        # 実装: FINCODE APIで返金処理
        result = fincode_service.refund_payment(payment_id, amount, reason)
        
        if result.get('success', False):
            return JsonResponse({
                "success": True,
                "fincode": result,
                "refund_id": result.get("refund_id"),
                "refund_amount": result.get("refund_amount"),
                "status": result.get("status")
            })
        else:
            return JsonResponse({
                "success": False,
                "error": "REFUND_FAILED", 
                "detail": "返金処理に失敗しました"
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "INVALID_JSON"}, status=400)
    except Exception as e:
        logger.error(f"❌ Refund error: {str(e)}")
        return JsonResponse({"success": False, "error": "REFUND_ERROR", "detail": str(e)}, status=500)


@csrf_exempt
def payment_return(request, order_id):
    """決済完了時のリターンURL"""
    logger.info(f"🔄 Payment return: order_id={order_id}")
    
    # 決済完了後の処理をここに実装
    # 例：データベースのステータス更新、ポイント付与など
    
    return JsonResponse({
        "success": True, 
        "message": "Payment completed", 
        "order_id": order_id,
        "next_action": "redirect_to_terminal"
    })


@csrf_exempt 
def payment_cancel(request, order_id):
    """決済キャンセル時のキャンセルURL"""
    logger.info(f"🔄 Payment cancelled: order_id={order_id}")
    
    # キャンセル処理をここに実装
    # 例：データベースのステータス更新
    
    return JsonResponse({
        "success": False, 
        "message": "Payment cancelled", 
        "order_id": order_id,
        "next_action": "redirect_to_terminal"
    })


@csrf_exempt
@require_POST
def payment_notify(request):
    """決済通知受信（Webhook）"""
    logger.info(f"🔄 Payment notification received")
    
    try:
        # FINCODE からの通知を処理
        body = json.loads(request.body.decode()) if request.body else {}
        payment_id = body.get('id', '')
        status = body.get('status', '')
        order_id = body.get('order_id', '')
        
        logger.info(f"📬 Webhook: payment_id={payment_id}, status={status}, order_id={order_id}")
        
        # データベース更新処理
        if payment_id and status:
            try:
                transaction = PaymentTransaction.objects.filter(
                    fincode_payment_id=payment_id
                ).first()
                
                if transaction:
                    # ステータスマッピング
                    status_map = {
                        'UNPROCESSED': 'pending',
                        'AUTHORIZED': 'processing', 
                        'CAPTURED': 'completed',
                        'CANCELED': 'cancelled',
                        'FAILED': 'failed'
                    }
                    
                    new_status = status_map.get(status, 'failed')
                    transaction.status = new_status
                    
                    if new_status == 'completed':
                        transaction.mark_completed()
                    else:
                        transaction.save()
                    
                    logger.info(f"✅ Transaction updated: {transaction.id} -> {new_status}")
                else:
                    logger.warning(f"⚠️ Transaction not found for payment_id: {payment_id}")
                    
            except Exception as e:
                logger.error(f"❌ Database update error: {str(e)}")
        
        return JsonResponse({"success": True, "message": "Notification processed"})
        
    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON in webhook")
        return JsonResponse({"success": False, "error": "INVALID_JSON"}, status=400)
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}")
        return JsonResponse({"success": False, "error": "WEBHOOK_ERROR"}, status=500)


@csrf_exempt
def get_transaction_history(request):
    """取引履歴取得API"""
    try:
        customer_id = request.GET.get('customer_id')
        limit = int(request.GET.get('limit', 20))
        
        if not customer_id:
            return JsonResponse({
                'success': False,
                'error': '顧客IDが必要です'
            }, status=400)
        
        # FINCODE決済取引履歴取得
        transactions = PaymentTransaction.objects.filter(
            customer__member_id=customer_id,
            payment_method='fincode'
        ).order_by('-created_at')[:limit]
        
        serializer = PaymentTransactionSerializer(transactions, many=True)
        
        return JsonResponse({
            'success': True,
            'transactions': serializer.data,
            'count': len(serializer.data)
        })
        
    except Exception as e:
        logger.error(f"❌ Transaction history error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'サーバーエラーが発生しました',
            'detail': str(e)
        }, status=500)


def mock_payment_page(request, order_id):
    """
    モック決済ページ
    実際の決済処理をシミュレートするHTMLページを返す
    """
    method = request.GET.get('method', 'card')
    amount = request.GET.get('amount', '0')
    
    # パラメータログ
    logger.info(f"🎭 Mock payment page accessed: order_id={order_id}, method={method}, amount={amount}")
    
    # 決済ページHTMLを返す
    html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FINCODE モック決済ページ - {method.upper()}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            max-width: 400px; 
            margin: 50px auto; 
            padding: 20px; 
            background: #f5f5f5; 
        }}
        .payment-card {{ 
            background: white; 
            padding: 30px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            text-align: center; 
        }}
        .brand-logo {{ 
            font-size: 24px; 
            font-weight: bold; 
            color: #2c3e50; 
            margin-bottom: 20px; 
        }}
        .amount {{ 
            font-size: 36px; 
            color: #e74c3c; 
            margin: 20px 0; 
        }}
        .btn {{
            background: #3498db;
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 16px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px;
            min-width: 120px;
        }}
        .btn:hover {{ background: #2980b9; }}
        .btn.success {{ background: #27ae60; }}
        .btn.success:hover {{ background: #229954; }}
        .btn.cancel {{ background: #e74c3c; }}
        .btn.cancel:hover {{ background: #c0392b; }}
        .order-info {{ 
            background: #ecf0f1; 
            padding: 15px; 
            border-radius: 5px; 
            margin-bottom: 20px; 
            font-size: 14px; 
            color: #555; 
        }}
        .fincode-brand {{
            color: #3498db;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="payment-card">
        <div class="brand-logo"><span class="fincode-brand">FINCODE</span> モック決済</div>
        <div class="order-info">
            <strong>注文ID:</strong> {order_id}<br>
            <strong>決済方法:</strong> {method.upper()}<br>
            <strong>決済サービス:</strong> GMO FINCODE
        </div>
        <div class="amount">¥{amount}</div>
        <p>これはテスト用の決済ページです。<br>実際の決済は行われません。</p>
        <div>
            <button class="btn success" onclick="simulateSuccess()">決済成功</button>
            <button class="btn cancel" onclick="simulateCancel()">決済キャンセル</button>
        </div>
        <div style="margin-top: 20px; font-size: 12px; color: #7f8c8d;">
            <p>🔧 開発モード: FINCODE統合テスト</p>
        </div>
    </div>
    
    <script>
        function simulateSuccess() {{
            alert('決済成功をシミュレートしています...');
            // 元の画面に戻る（実際の実装ではreturn_urlにリダイレクト）
            setTimeout(() => {{
                window.location.href = 'http://localhost:3000/terminal-simple?payment=return&order_id={order_id}&status=success&gateway=fincode';
            }}, 1000);
        }}
        
        function simulateCancel() {{
            alert('決済キャンセルをシミュレートしています...');
            // 元の画面に戻る（実際の実装ではcancel_urlにリダイレクト）
            setTimeout(() => {{
                window.location.href = 'http://localhost:3000/terminal-simple?payment=cancel&order_id={order_id}&status=cancel&gateway=fincode';
            }}, 1000);
        }}
        
        // 自動リダイレクトオプション（15秒後）
        setTimeout(() => {{
            if (confirm('15秒経過しました。自動で決済成功として処理しますか？')) {{
                simulateSuccess();
            }}
        }}, 15000);
    </script>
</body>
</html>
    """
    
    return HttpResponse(html_content, content_type='text/html')