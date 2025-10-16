from rest_framework import serializers
from decimal import Decimal
from .models import DepositTransaction, DepositAutoChargeRule, DepositUsageLog


class DepositTransactionSerializer(serializers.ModelSerializer):
    """デポジット取引シリアライザー"""
    
    class Meta:
        model = DepositTransaction
        fields = [
            'id', 'transaction_id', 'transaction_type', 'amount',
            'balance_before', 'balance_after', 'payment_method',
            'payment_reference', 'fee_amount', 'fee_rate',
            'description', 'status', 'created_at', 'processed_at'
        ]
        read_only_fields = [
            'id', 'transaction_id', 'balance_before', 'balance_after',
            'created_at', 'processed_at'
        ]


class DepositChargeSerializer(serializers.Serializer):
    """デポジットチャージリクエストシリアライザー"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1000'))
    payment_method = serializers.CharField(max_length=50)
    payment_reference = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)


class DepositConsumeSerializer(serializers.Serializer):
    """デポジット消費リクエストシリアライザー"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1'))
    used_for = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    user_count = serializers.IntegerField(min_value=0, required=False, default=0)


class DepositAutoChargeRuleSerializer(serializers.ModelSerializer):
    """自動チャージルールシリアライザー"""
    
    class Meta:
        model = DepositAutoChargeRule
        fields = [
            'id', 'trigger_amount', 'charge_amount', 'payment_method',
            'payment_reference', 'max_charge_per_day', 'max_charge_per_month',
            'notification_email', 'is_enabled', 'last_triggered_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_triggered_at', 'created_at', 'updated_at']


class AutoChargeSetupSerializer(serializers.Serializer):
    """自動チャージ設定リクエストシリアライザー"""
    trigger_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    charge_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1000'))
    payment_method = serializers.CharField(max_length=50)
    payment_reference = serializers.CharField(max_length=200, required=False, allow_blank=True)
    max_charge_per_day = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    max_charge_per_month = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    notification_email = serializers.EmailField(required=False, allow_blank=True)


class DepositUsageLogSerializer(serializers.ModelSerializer):
    """デポジット使用履歴シリアライザー"""
    
    class Meta:
        model = DepositUsageLog
        fields = [
            'id', 'transaction', 'used_for', 'used_amount',
            'related_promotion', 'user_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DepositBalanceSerializer(serializers.Serializer):
    """デポジット残高情報シリアライザー"""
    current_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    recent_transactions = DepositTransactionSerializer(many=True, read_only=True)
    month_stats = serializers.DictField(read_only=True)
    auto_charge_info = serializers.DictField(read_only=True, allow_null=True)