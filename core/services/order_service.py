import hashlib
import json
from decimal import Decimal
from django.db import transaction, connection, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core.models import Dealer, Product, Order, OrderItem, OrderStatus, IdempotencyRecord, InventoryLog
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


def _validate_items(items_data: list[dict]) -> tuple[list[tuple[str, int]], dict[str, Product]]:
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
        if quantity is None or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            raise ContractAPIException(
                message=f"Quantity for SKU '{sku}' must be an integer >= 1.",
                details=[f"item[{idx}].quantity must be an integer >= 1"],
            )
        sku_quantities.append((sku, quantity))

    products_by_sku = {p.sku: p for p in Product.objects.filter(sku__in=seen_skus)}
    for sku, _ in sku_quantities:
        if sku not in products_by_sku:
            raise ContractAPIException(
                message=f"Product with SKU '{sku}' does not exist.",
                details=[f"Unknown SKU: {sku}"],
            )

    return sku_quantities, products_by_sku


def _execute_create_order(dealer_id: int, items_data: list[dict], idempotency_key: str = None, req_hash: str = None) -> tuple[Order, bool]:
    dealer = Dealer.objects.filter(id=dealer_id).first()
    if not dealer:
        raise ContractAPIException(
            message=f"Dealer with id {dealer_id} does not exist.",
            details=[f"dealer_id: {dealer_id} not found"],
        )

    sku_quantities, products_by_sku = _validate_items(items_data)

    with transaction.atomic():
        order_number = get_next_order_number()

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
            try:
                IdempotencyRecord.objects.create(
                    key=idempotency_key,
                    request_hash=req_hash,
                    order=order,
                )
            except IntegrityError:
                existing = IdempotencyRecord.objects.filter(key=idempotency_key).first()
                if existing and existing.request_hash == req_hash:
                    order.delete()
                    return existing.order, False
                else:
                    order.delete()
                    raise IdempotencyConflictError(
                        message="Idempotency-Key reused with different request payload.",
                        details=["The payload does not match the previous request for this idempotency key."],
                    )

        return order, True


def create_draft_order(dealer_id: int, items_data: list[dict], idempotency_key: str = None) -> tuple[Order, bool]:
    body_payload = {"dealer_id": dealer_id, "items": items_data}
    req_hash = hash_request_body(body_payload)

    if idempotency_key:
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"idem_{idempotency_key}"])

            existing_record = IdempotencyRecord.objects.select_for_update().filter(key=idempotency_key).first()
            if existing_record:
                if existing_record.request_hash == req_hash:
                    return existing_record.order, False
                else:
                    raise IdempotencyConflictError(
                        message="Idempotency-Key reused with different request payload.",
                        details=["The payload does not match the previous request for this idempotency key."],
                    )

            return _execute_create_order(dealer_id, items_data, idempotency_key, req_hash)

    return _execute_create_order(dealer_id, items_data, None, None)


def update_draft_order_items(order_number: str, items_data: list[dict]) -> Order:
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(order_number=order_number).first()
        if not order:
            raise NotFound(detail=f"Order '{order_number}' not found.")

        if order.status != OrderStatus.DRAFT:
            raise OrderLockedError(
                message=f"Cannot edit order in '{order.status}' status. Only DRAFT orders can be edited.",
                details=[f"Order status is {order.status}"],
            )

        sku_quantities, products_by_sku = _validate_items(items_data)

        order.items.all().delete()

        lines_calc = []
        for sku, qty in sku_quantities:
            prod = products_by_sku[sku]
            line_data = calculate_line(prod.price, qty)
            line_data["sku"] = sku
            line_data["name"] = prod.name
            line_data["product"] = prod
            lines_calc.append(line_data)

        totals = calculate_order_totals(lines_calc)

        order.subtotal = totals["subtotal"]
        order.tax_total = totals["tax_total"]
        order.grand_total = totals["grand_total"]
        order.save(update_fields=["subtotal", "tax_total", "grand_total", "updated_at"])

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

        if hasattr(order, "_cached_pricing_data"):
            delattr(order, "_cached_pricing_data")

        return order


def confirm_order(order_number: str) -> Order:
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(order_number=order_number).first()
        if not order:
            raise NotFound(detail=f"Order '{order_number}' not found.")

        if order.status != OrderStatus.DRAFT:
            raise InvalidTransitionError(
                message=f"Cannot confirm order in '{order.status}' status.",
                details=[f"Current status is {order.status}, expected DRAFT"],
            )

        items = list(order.items.select_related("product").all())
        if not items:
            raise ContractAPIException(
                message="Cannot confirm an empty order.",
                details=["Order has no items"],
            )

        # Sort SKUs to prevent deadlocks across concurrent confirmations
        sku_list = sorted([item.sku for item in items])
        products_locked = {
            p.sku: p
            for p in Product.objects.select_for_update().filter(sku__in=sku_list).order_by("sku")
        }

        # Check stock for all items (All-or-nothing check)
        short_lines = []
        messages = []
        for item in items:
            prod = products_locked.get(item.sku)
            avail = prod.stock if prod else 0
            if avail < item.quantity:
                short_lines.append({
                    "sku": item.sku,
                    "requested": item.quantity,
                    "available": avail,
                })
                prod_name = prod.name if prod else item.name
                messages.append(f"Insufficient stock for {prod_name}. Available: {avail}, Requested: {item.quantity}")

        if short_lines:
            raise InsufficientStockError(
                message=". ".join(messages),
                details=short_lines,
            )

        # Deduct stock and lock pricing permanently
        lines_calc = []
        for item in items:
            prod = products_locked[item.sku]
            prod.stock -= item.quantity
            prod.save(update_fields=["stock", "updated_at"])

            InventoryLog.objects.create(
                product=prod,
                quantity=-item.quantity,
                reason=f"ORDER_CONFIRM: {order.order_number}",
            )

            # Permanent price locking
            line_calc = calculate_line(prod.price, item.quantity)
            item.unit_price = line_calc["unit_price"]
            item.line_subtotal = line_calc["line_subtotal"]
            item.line_tax = line_calc["line_tax"]
            item.line_total = line_calc["line_total"]
            item.save(update_fields=["unit_price", "line_subtotal", "line_tax", "line_total"])
            lines_calc.append(line_calc)

        totals = calculate_order_totals(lines_calc)
        order.subtotal = totals["subtotal"]
        order.tax_total = totals["tax_total"]
        order.grand_total = totals["grand_total"]
        order.status = OrderStatus.CONFIRMED
        order.save(update_fields=["status", "subtotal", "tax_total", "grand_total", "updated_at"])

        if hasattr(order, "_cached_pricing_data"):
            delattr(order, "_cached_pricing_data")

        return order


def dispatch_order(order_number: str) -> Order:
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(order_number=order_number).first()
        if not order:
            raise NotFound(detail=f"Order '{order_number}' not found.")

        if order.status != OrderStatus.CONFIRMED:
            raise InvalidTransitionError(
                message=f"Cannot dispatch order in '{order.status}' status.",
                details=[f"Current status is {order.status}, expected CONFIRMED"],
            )

        order.status = OrderStatus.DISPATCHED
        order.save(update_fields=["status", "updated_at"])

        if hasattr(order, "_cached_pricing_data"):
            delattr(order, "_cached_pricing_data")

        return order


def deliver_order(order_number: str) -> Order:
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(order_number=order_number).first()
        if not order:
            raise NotFound(detail=f"Order '{order_number}' not found.")

        if order.status != OrderStatus.DISPATCHED:
            raise InvalidTransitionError(
                message=f"Cannot deliver order in '{order.status}' status.",
                details=[f"Order status is {order.status}, expected DISPATCHED"],
            )

        order.status = OrderStatus.DELIVERED
        order.save(update_fields=["status", "updated_at"])

        if hasattr(order, "_cached_pricing_data"):
            delattr(order, "_cached_pricing_data")

        return order


def cancel_order(order_number: str) -> Order:
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(order_number=order_number).first()
        if not order:
            raise NotFound(detail=f"Order '{order_number}' not found.")

        if order.status not in (OrderStatus.DRAFT, OrderStatus.CONFIRMED):
            raise InvalidTransitionError(
                message=f"Cannot cancel order in '{order.status}' status.",
                details=[f"Current status is {order.status}. Only DRAFT or CONFIRMED orders can be cancelled."],
            )

        if order.status == OrderStatus.CONFIRMED:
            items = list(order.items.select_related("product").all())
            sku_list = sorted([item.sku for item in items])
            products_locked = {
                p.sku: p
                for p in Product.objects.select_for_update().filter(sku__in=sku_list).order_by("sku")
            }
            for item in items:
                prod = products_locked.get(item.sku)
                if prod:
                    prod.stock += item.quantity
                    prod.save(update_fields=["stock", "updated_at"])
                    InventoryLog.objects.create(
                        product=prod,
                        quantity=item.quantity,
                        reason=f"ORDER_CANCEL: {order.order_number}",
                    )

        order.status = OrderStatus.CANCELLED
        order.save(update_fields=["status", "updated_at"])

        if hasattr(order, "_cached_pricing_data"):
            delattr(order, "_cached_pricing_data")

        return order
