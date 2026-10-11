from decimal import Decimal, InvalidOperation
from rest_framework import serializers

from core.models import Product, Dealer, Order, OrderItem
from core.exceptions import DuplicateError, ContractAPIException


class TwoDecimalField(serializers.DecimalField):
    """Ensures monetary values are serialized as two-decimal strings (e.g. '1459.50')."""
    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("coerce_to_string", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value is None:
            return None
        return f"{Decimal(str(value)):.2f}"


def validate_price_value(value):
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ContractAPIException(
            message="Price must be a valid positive number with at most 2 decimal places.",
            details=["price is not a valid number"],
        )

    if dec <= 0:
        raise ContractAPIException(
            message="Price must be greater than 0.",
            details=["price must be > 0"],
        )

    # Check at most 2 decimal places
    parts = str(value).split(".")
    if len(parts) == 2 and len(parts[1]) > 2:
        raise ContractAPIException(
            message="Price can have at most 2 decimal places.",
            details=["price precision exceeds 2 decimal places"],
        )
    return dec


class ProductSerializer(serializers.ModelSerializer):
    price = TwoDecimalField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "stock",
            "description",
        ]
        read_only_fields = ["stock"]


class ProductCreateSerializer(serializers.ModelSerializer):
    price = serializers.CharField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_sku(self, value):
        if not value or not str(value).strip():
            raise ContractAPIException(
                message="SKU is required and cannot be empty.",
                details=["sku cannot be blank"],
            )
        sku_clean = str(value).strip()
        if Product.objects.filter(sku=sku_clean).exists():
            raise DuplicateError(
                message=f"Product with SKU '{sku_clean}' already exists.",
                details=[f"sku: {sku_clean} is a duplicate"],
            )
        return sku_clean

    def validate_price(self, value):
        return validate_price_value(value)

    def create(self, validated_data):
        validated_data["stock"] = 0
        return Product.objects.create(**validated_data)


class ProductUpdateSerializer(serializers.ModelSerializer):
    price = serializers.CharField(required=False)

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_price(self, value):
        return validate_price_value(value)


class DealerSerializer(serializers.ModelSerializer):
    credit_limit = TwoDecimalField(required=False, default=Decimal("0.00"))

    class Meta:
        model = Dealer
        fields = [
            "id",
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]
        read_only_fields = ["id"]

    def validate_dealer_code(self, value):
        if not value or not str(value).strip():
            raise ContractAPIException(
                message="dealer_code is required.",
                details=["dealer_code cannot be empty"],
            )
        code_clean = str(value).strip()
        instance = getattr(self, "instance", None)
        qs = Dealer.objects.filter(dealer_code=code_clean)
        if instance:
            qs = qs.exclude(id=instance.id)
        if qs.exists():
            raise DuplicateError(
                message=f"Dealer with code '{code_clean}' already exists.",
                details=[f"dealer_code: {code_clean} is a duplicate"],
            )
        return code_clean


class OrderItemSerializer(serializers.ModelSerializer):
    unit_price = TwoDecimalField()
    line_subtotal = TwoDecimalField()
    line_tax = TwoDecimalField()
    line_total = TwoDecimalField()

    class Meta:
        model = OrderItem
        fields = [
            "sku",
            "name",
            "quantity",
            "unit_price",
            "line_subtotal",
            "line_tax",
            "line_total",
        ]


class OrderSerializer(serializers.ModelSerializer):
    dealer_id = serializers.IntegerField(source="dealer.id")
    items = OrderItemSerializer(many=True, read_only=True)
    subtotal = TwoDecimalField()
    tax_total = TwoDecimalField()
    grand_total = TwoDecimalField()
    created_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S%z")
    updated_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S%z")

    class Meta:
        model = Order
        fields = [
            "order_number",
            "dealer_id",
            "status",
            "items",
            "subtotal",
            "tax_total",
            "grand_total",
            "created_at",
            "updated_at",
        ]
