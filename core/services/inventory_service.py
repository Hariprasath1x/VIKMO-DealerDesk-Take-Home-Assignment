from django.db import transaction
from core.models import Product, InventoryLog
from core.exceptions import ContractAPIException
from rest_framework.exceptions import NotFound


def update_inventory(sku: str, quantity: int, reason: str = "") -> dict:
    if quantity is None or not isinstance(quantity, int) or quantity < 0:
        raise ContractAPIException(
            message="Quantity must be an integer >= 0.",
            details=["quantity must be an integer >= 0"],
        )

    with transaction.atomic():
        product = Product.objects.select_for_update().filter(sku=sku).first()
        if not product:
            raise NotFound(detail=f"Product with SKU '{sku}' not found.")

        product.stock = quantity
        product.save(update_fields=["stock", "updated_at"])

        InventoryLog.objects.create(
            product=product,
            quantity=quantity,
            reason=reason or "stock count correction",
        )

    return {"sku": product.sku, "quantity": product.stock}
