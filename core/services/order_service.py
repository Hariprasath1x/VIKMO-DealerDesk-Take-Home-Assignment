import hashlib
import json
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from core.models import Dealer, Product, Order, OrderItem, OrderStatus, IdempotencyRecord
from core.exceptions import (
    ContractAPIException,
    IdempotencyConflictError,
    InsufficientStockError,
    InvalidTransitionError,
    OrderLockedError,
)
from core.services.pricing_service import calculate_line, calculate_order_totals
from core.services.sequence_service import get_next_order_number


def hash_request_body(body_data: dict) -> str:
    canonical = json.dumps(body_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_draft_order(dealer_id: int, items_data: list[dict], idempotency_key: str = None) -> tuple[Order, bool]:
    """
    Creates a draft order adhering to contract section 7.1 and 7.5.
    Returns (order, created: bool).
    """
    body_payload = {"dealer_id": dealer_id, "items": items_data}
    req_hash = hash_request_body(body_payload)

    if idempotency_key:
        with transaction.atomic():
            existing_record = IdempotencyRecord.objects.select_for_update().filter(key=idempotency_key).first()
            if existing_record:
                if existing_record.request_hash == req_hash:
                    return existing_record.order, False
                else:
                    raise IdempotencyConflictError(
                        message="Idempotency-Key reused with different request payload.",
                        details=["The payload does not match the previous request for this idempotency key."],
                    )

    # 1. Validate dealer exists
    dealer = Dealer.objects.filter(id=dealer_id).first()
    if not dealer:
        raise ContractAPIException(
            message=f"Dealer with id {dealer_id} does not exist.",
            details=[f"dealer_id: {dealer_id} not found"],
        )

    # 2. Validate items
    if not items_data or not isinstance(items_data, list):
        raise ContractAPIException(
            message="Order must contain at least one item.",
            details=["items: at least one item is required"],
        )

    seen_skus = set()
    sku_quantities = []
    for idx, item in enumerate(items_data):
        if not isinstance(item, dict):
            raise ContractAPIException(
                message="Invalid item format.",
                details=[f"item[{idx}] must be an object"],
            )
        sku = item.get("sku")
        if not sku or not isinstance(sku, str):
            raise ContractAPIException(
                message="Every line item must include a valid SKU.",
                details=[f"item[{idx}].sku is required"],
            )
        if sku in seen_skus:
            raise ContractAPIException(
                message=f"Duplicate SKU '{sku}' found in order items.",
                details=[f"SKU {sku} appeared more than once in items"],
            )
        seen_skus.add(sku)

        quantity = item.get("quantity")
        if quantity is None or not isinstance(quantity, int) or quantity < 1:
            raise ContractAPIException(
                message=f"Quantity for SKU '{sku}' must be an integer >= 1.",
                details=[f"item[{idx}].quantity must be an integer >= 1"],
            )
        sku_quantities.append((sku, quantity))

    # 3. Validate SKUs exist in catalogue
    products_by_sku = {p.sku: p for p in Product.objects.filter(sku__in=seen_skus)}
    for sku, _ in sku_quantities:
        if sku not in products_by_sku:
            raise ContractAPIException(
                message=f"Product with SKU '{sku}' does not exist.",
                details=[f"Unknown SKU: {sku}"],
            )

    # 4. Atomic order creation
    with transaction.atomic():
        order_number = get_next_order_number()

        # Build lines
        lines_calc = []
        for sku, qty in sku_quantities:
            prod = products_by_sku[sku]
            line_data = calculate_line(prod.price, qty)
            line_data["sku"] = sku
            line_data["name"] = prod.name
            line_data["product"] = prod
            lines_calc.append(line_data)

        totals = calculate_order_totals(lines_calc)

        order = Order.objects.create(
            order_number=order_number,
            dealer=dealer,
            status=OrderStatus.DRAFT,
            subtotal=totals["subtotal"],
            tax_total=totals["tax_total"],
            grand_total=totals["grand_total"],
        )

        for line in lines_calc:
            OrderItem.objects.create(
                order=order,
                product=line["product"],
                sku=line["sku"],
                name=line["name"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                line_subtotal=line["line_subtotal"],
                line_tax=line["line_tax"],
                line_total=line["line_total"],
            )

        if idempotency_key:
            IdempotencyRecord.objects.create(
                key=idempotency_key,
                request_hash=req_hash,
                order=order,
            )

    return order, True
