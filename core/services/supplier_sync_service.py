import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import requests
from django.conf import settings
from django.db import transaction

from core.models import Product
from core.exceptions import SupplierUnavailableError


def parse_iso_datetime(dt_str: str) -> datetime:
    if not dt_str or not isinstance(dt_str, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        clean = dt_str.strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        return datetime.fromisoformat(clean)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def run_supplier_sync(
    api_url: str = None,
    api_key: str = None,
    max_retries: int = 5,
    timeout: float = 10.0,
) -> dict:
    """
    Executes a complete supplier catalogue synchronization per API contract section 8.
    Stage 1: Fetch and validate all pages from supplier API with bounded retries.
    Stage 2: Reconcile and apply changes atomically into PostgreSQL without altering stock.
    """
    if not api_url:
        api_url = getattr(settings, "SUPPLIER_API_URL", None) or os.environ.get(
            "SUPPLIER_API_URL", "http://127.0.0.1:8099"
        )
    if not api_key:
        api_key = getattr(settings, "SUPPLIER_API_KEY", None) or os.environ.get(
            "SUPPLIER_API_KEY", "dev-supplier-key"
        )

    api_url = api_url.rstrip("/")
    endpoint = f"{api_url}/v1/products"
    headers = {"X-Api-Key": api_key}

    cursor = None
    seen_cursors = set()
    raw_items = []
    pages_fetched = 0
    requests_made = 0

    # -------------------------------------------------------------
    # STAGE 1: Fetch all pages with bounded retries (All-or-Nothing)
    # -------------------------------------------------------------
    while True:
        params = {"limit": 20}
        if cursor is not None:
            params["cursor"] = cursor

        success = False
        last_error_detail = ""

        for attempt in range(1, max_retries + 1):
            requests_made += 1
            try:
                resp = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    page_items = data.get("items", [])
                    raw_items.extend(page_items)
                    pages_fetched += 1
                    next_cursor = data.get("next_cursor")
                    success = True
                    break

                elif resp.status_code == 401:
                    raise SupplierUnavailableError(
                        message="Supplier API key rejected (401 Unauthorized).",
                        details=["Supplier responded with 401: invalid or missing API key."],
                    )

                elif resp.status_code == 429:
                    retry_after_hdr = resp.headers.get("Retry-After")
                    try:
                        wait = max(0.1, float(retry_after_hdr)) if retry_after_hdr else 1.0
                    except (ValueError, TypeError):
                        wait = 1.0

                    last_error_detail = f"Rate limited (429), Retry-After={wait}"
                    if attempt < max_retries:
                        time.sleep(wait)
                        continue

                elif resp.status_code in (500, 502, 503, 504):
                    last_error_detail = f"Server error ({resp.status_code})"
                    if attempt < max_retries:
                        backoff = min(4.0, 0.2 * (2 ** (attempt - 1)))
                        time.sleep(backoff)
                        continue

                else:
                    last_error_detail = f"Unexpected status {resp.status_code}: {resp.text[:100]}"
                    if attempt < max_retries:
                        time.sleep(0.5)
                        continue

            except requests.RequestException as e:
                last_error_detail = f"Connection error: {str(e)}"
                if attempt < max_retries:
                    backoff = min(4.0, 0.2 * (2 ** (attempt - 1)))
                    time.sleep(backoff)
                    continue

        if not success:
            raise SupplierUnavailableError(
                message="Supplier feed could not be fetched.",
                details=[
                    f"Failed to fetch page at cursor '{cursor}' after {max_retries} attempts. Last error: {last_error_detail}"
                ],
            )

        if not next_cursor:
            break

        if next_cursor in seen_cursors:
            raise SupplierUnavailableError(
                message="Supplier feed could not be fetched.",
                details=[f"Loop detected in pagination cursor: '{next_cursor}' already visited."],
            )

        seen_cursors.add(next_cursor)
        cursor = next_cursor

    # -------------------------------------------------------------
    # STAGE 2: Validate items & filter invalid into rejected
    # -------------------------------------------------------------
    rejected = []
    valid_items = []

    for item in raw_items:
        supplier_sku = str(item.get("supplier_sku") or "")
        sku = item.get("sku")

        # SKU validation: required non-empty string
        if not sku or not isinstance(sku, str) or not sku.strip():
            rejected.append({"supplier_sku": supplier_sku, "reason": "missing sku"})
            continue
        clean_sku = sku.strip()

        # Price validation: positive decimal with at most 2 decimal places
        price_val = item.get("price")
        try:
            if price_val is None:
                raise ValueError("missing price")
            price_dec = Decimal(str(price_val))
            if price_dec <= Decimal("0.00"):
                raise ValueError("price must be positive")
            parts = str(price_val).split(".")
            if len(parts) == 2 and len(parts[1]) > 2:
                raise ValueError("price has more than 2 decimal places")
        except (InvalidOperation, TypeError, ValueError):
            rejected.append({"supplier_sku": supplier_sku, "reason": "invalid price"})
            continue

        valid_items.append({
            "supplier_sku": supplier_sku,
            "sku": clean_sku,
            "name": str(item.get("name") or "").strip(),
            "category": str(item.get("category") or "").strip(),
            "brand": str(item.get("brand") or "").strip(),
            "vehicle_fitment": str(item.get("vehicle_fitment") or "").strip(),
            "description": str(item.get("description") or "").strip(),
            "price_dec": price_dec,
            "parsed_updated_at": parse_iso_datetime(item.get("updated_at")),
        })

    # -------------------------------------------------------------
    # STAGE 3: Deduplicate by SKU using latest updated_at
    # -------------------------------------------------------------
    unique_items_by_sku = {}
    for item in valid_items:
        sku = item["sku"]
        if sku not in unique_items_by_sku:
            unique_items_by_sku[sku] = item
        else:
            prev = unique_items_by_sku[sku]
            if item["parsed_updated_at"] > prev["parsed_updated_at"]:
                unique_items_by_sku[sku] = item

    # -------------------------------------------------------------
    # STAGE 4: Reconcile and apply changes atomically
    # -------------------------------------------------------------
    created = 0
    updated = 0
    unchanged = 0

    with transaction.atomic():
        existing_products = {
            p.sku: p
            for p in Product.objects.filter(sku__in=list(unique_items_by_sku.keys()))
        }

        for sku, item in unique_items_by_sku.items():
            if sku not in existing_products:
                Product.objects.create(
                    sku=sku,
                    name=item["name"],
                    category=item["category"],
                    brand=item["brand"],
                    vehicle_fitment=item["vehicle_fitment"],
                    description=item["description"],
                    price=item["price_dec"],
                    stock=0,  # Never initialize stock from supplier warehouse quantity
                )
                created += 1
            else:
                prod = existing_products[sku]
                needs_update = False
                update_fields = []

                if prod.name != item["name"]:
                    prod.name = item["name"]
                    needs_update = True
                    update_fields.append("name")

                if prod.category != item["category"]:
                    prod.category = item["category"]
                    needs_update = True
                    update_fields.append("category")

                if prod.brand != item["brand"]:
                    prod.brand = item["brand"]
                    needs_update = True
                    update_fields.append("brand")

                if prod.vehicle_fitment != item["vehicle_fitment"]:
                    prod.vehicle_fitment = item["vehicle_fitment"]
                    needs_update = True
                    update_fields.append("vehicle_fitment")

                if prod.description != item["description"]:
                    prod.description = item["description"]
                    needs_update = True
                    update_fields.append("description")

                if prod.price != item["price_dec"]:
                    prod.price = item["price_dec"]
                    needs_update = True
                    update_fields.append("price")

                if needs_update:
                    update_fields.append("updated_at")
                    prod.save(update_fields=update_fields)
                    updated += 1
                else:
                    unchanged += 1

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "rejected": rejected,
        "pages_fetched": pages_fetched,
        "requests_made": requests_made,
    }
