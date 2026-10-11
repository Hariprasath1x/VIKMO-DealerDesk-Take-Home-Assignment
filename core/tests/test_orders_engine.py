import concurrent.futures
from decimal import Decimal
from django.test import TransactionTestCase
from django.db import connections
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Product, Dealer, Order, OrderItem, OrderStatus, InventoryLog, IdempotencyRecord
from core.services.sequence_service import get_next_order_number


class OrderEngineLifecycleTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-TEST-01",
            name="Alpha Motors",
            city="Chennai",
            phone="9876543210",
            email="alpha@example.com",
            gstin="33AAAAA0000A1Z5",
            credit_limit=Decimal("500000.00"),
        )
        self.p1 = Product.objects.create(
            sku="TST-101",
            name="Front Brake Disc",
            category="Brakes",
            brand="Brembo",
            vehicle_fitment="KTM Duke 390",
            price=Decimal("1459.50"),
            stock=20,
            description="High performance disc",
        )
        self.p2 = Product.objects.create(
            sku="TST-102",
            name="Oil Filter",
            category="Filters",
            brand="Bosch",
            vehicle_fitment="Universal",
            price=Decimal("250.25"),
            stock=10,
            description="OEM oil filter",
        )

    def tearDown(self):
        connections.close_all()

    def test_gst_calculation_and_round_half_up(self):
        """
        Verify exact GST calculation:
        line_subtotal = price * qty
        line_tax = line_subtotal * 0.18 rounded ROUND_HALF_UP (0.005 -> 0.01)
        subtotal = sum(line_subtotal), tax_total = sum(line_tax), grand_total = subtotal + tax_total
        """
        resp = self.client.post(
            "/api/orders/",
            {
                "dealer_id": self.dealer.id,
                "items": [
                    {"sku": self.p1.sku, "quantity": 3},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data

        # 1459.50 * 3 = 4378.50
        # 4378.50 * 0.18 = 788.1300 -> 788.13
        # 4378.50 + 788.13 = 5166.63
        self.assertEqual(data["items"][0]["unit_price"], "1459.50")
        self.assertEqual(data["items"][0]["line_subtotal"], "4378.50")
        self.assertEqual(data["items"][0]["line_tax"], "788.13")
        self.assertEqual(data["items"][0]["line_total"], "5166.63")
        self.assertEqual(data["subtotal"], "4378.50")
        self.assertEqual(data["tax_total"], "788.13")
        self.assertEqual(data["grand_total"], "5166.63")

    def test_draft_dynamic_price_changes_and_lock_at_confirmation(self):
        """
        While DRAFT, order reflects current catalogue price.
        Upon CONFIRMATION, price is permanently locked and unaffected by future catalogue price changes.
        """
        resp = self.client.post(
            "/api/orders/",
            {
                "dealer_id": self.dealer.id,
                "items": [{"sku": self.p1.sku, "quantity": 2}],
            },
            format="json",
        )
        order_num = resp.data["order_number"]
        self.assertEqual(resp.data["items"][0]["unit_price"], "1459.50")
        self.assertEqual(resp.data["subtotal"], "2919.00")

        # 1. Update product price in catalogue while order is still DRAFT
        self.p1.price = Decimal("1600.00")
        self.p1.save(update_fields=["price"])

        # Fetch draft order: should immediately reflect updated catalogue price
        resp_draft = self.client.get(f"/api/orders/{order_num}/")
        self.assertEqual(resp_draft.status_code, status.HTTP_200_OK)
        # 1600.00 * 2 = 3200.00, tax = 3200 * 0.18 = 576.00, total = 3776.00
        self.assertEqual(resp_draft.data["items"][0]["unit_price"], "1600.00")
        self.assertEqual(resp_draft.data["subtotal"], "3200.00")
        self.assertEqual(resp_draft.data["tax_total"], "576.00")
        self.assertEqual(resp_draft.data["grand_total"], "3776.00")

        # 2. Confirm order: price locks at 1600.00
        resp_confirm = self.client.post(f"/api/orders/{order_num}/confirm/")
        self.assertEqual(resp_confirm.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_confirm.data["status"], "CONFIRMED")
        self.assertEqual(resp_confirm.data["items"][0]["unit_price"], "1600.00")

        # 3. Change product price again after confirmation
        self.p1.price = Decimal("2000.00")
        self.p1.save(update_fields=["price"])

        # Fetch confirmed order: must remain locked at agreed 1600.00!
        resp_after = self.client.get(f"/api/orders/{order_num}/")
        self.assertEqual(resp_after.data["items"][0]["unit_price"], "1600.00")
        self.assertEqual(resp_after.data["subtotal"], "3200.00")
        self.assertEqual(resp_after.data["grand_total"], "3776.00")

    def test_status_lifecycle_happy_path(self):
        """DRAFT -> CONFIRMED -> DISPATCHED -> DELIVERED"""
        resp = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 2}]},
            format="json",
        )
        order_num = resp.data["order_number"]
        self.assertEqual(resp.data["status"], "DRAFT")

        # Confirm
        resp_c = self.client.post(f"/api/orders/{order_num}/confirm/")
        self.assertEqual(resp_c.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_c.data["status"], "CONFIRMED")

        # Dispatch
        resp_d = self.client.post(f"/api/orders/{order_num}/dispatch/")
        self.assertEqual(resp_d.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_d.data["status"], "DISPATCHED")

        # Deliver
        resp_dl = self.client.post(f"/api/orders/{order_num}/deliver/")
        self.assertEqual(resp_dl.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_dl.data["status"], "DELIVERED")

    def test_invalid_status_transitions_rejected(self):
        """Ensure all illegal transitions return 409 INVALID_TRANSITION"""
        resp = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 1}]},
            format="json",
        )
        order_num = resp.data["order_number"]

        # DRAFT cannot jump directly to DISPATCHED or DELIVERED
        r1 = self.client.post(f"/api/orders/{order_num}/dispatch/")
        self.assertEqual(r1.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r1.data["error"]["code"], "INVALID_TRANSITION")

        r2 = self.client.post(f"/api/orders/{order_num}/deliver/")
        self.assertEqual(r2.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r2.data["error"]["code"], "INVALID_TRANSITION")

        # Confirm order
        self.client.post(f"/api/orders/{order_num}/confirm/")

        # CONFIRMED cannot be delivered directly (must dispatch first)
        r3 = self.client.post(f"/api/orders/{order_num}/deliver/")
        self.assertEqual(r3.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r3.data["error"]["code"], "INVALID_TRANSITION")

        # CONFIRMED cannot be confirmed again
        r4 = self.client.post(f"/api/orders/{order_num}/confirm/")
        self.assertEqual(r4.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r4.data["error"]["code"], "INVALID_TRANSITION")

        # Dispatch order
        self.client.post(f"/api/orders/{order_num}/dispatch/")

        # DISPATCHED cannot be cancelled
        r5 = self.client.post(f"/api/orders/{order_num}/cancel/")
        self.assertEqual(r5.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r5.data["error"]["code"], "INVALID_TRANSITION")

        # Deliver order
        self.client.post(f"/api/orders/{order_num}/deliver/")

        # DELIVERED cannot be cancelled
        r6 = self.client.post(f"/api/orders/{order_num}/cancel/")
        self.assertEqual(r6.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r6.data["error"]["code"], "INVALID_TRANSITION")

    def test_put_edit_only_allowed_on_draft(self):
        """PUT /api/orders/{order_number}/ replaces items while DRAFT, rejects with 409 ORDER_LOCKED once confirmed."""
        resp = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 1}]},
            format="json",
        )
        order_num = resp.data["order_number"]

        # Edit draft items
        resp_put = self.client.put(
            f"/api/orders/{order_num}/",
            {"items": [{"sku": self.p2.sku, "quantity": 4}]},
            format="json",
        )
        self.assertEqual(resp_put.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_put.data["items"]), 1)
        self.assertEqual(resp_put.data["items"][0]["sku"], self.p2.sku)
        self.assertEqual(resp_put.data["items"][0]["quantity"], 4)

        # Confirm order
        self.client.post(f"/api/orders/{order_num}/confirm/")

        # Try to edit confirmed order -> 409 ORDER_LOCKED
        resp_locked = self.client.put(
            f"/api/orders/{order_num}/",
            {"items": [{"sku": self.p1.sku, "quantity": 2}]},
            format="json",
        )
        self.assertEqual(resp_locked.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp_locked.data["error"]["code"], "ORDER_LOCKED")

    def test_insufficient_stock_all_or_nothing_rejection(self):
        """
        Confirmation must fail completely if any line exceeds available stock.
        Nothing is deducted, and response details lists every short line.
        """
        self.p1.stock = 5
        self.p1.save(update_fields=["stock"])
        self.p2.stock = 2
        self.p2.save(update_fields=["stock"])

        # Order requests 10 of p1 (avail 5) and 1 of p2 (avail 2)
        resp = self.client.post(
            "/api/orders/",
            {
                "dealer_id": self.dealer.id,
                "items": [
                    {"sku": self.p1.sku, "quantity": 10},
                    {"sku": self.p2.sku, "quantity": 1},
                ],
            },
            format="json",
        )
        order_num = resp.data["order_number"]

        # Try to confirm
        resp_conf = self.client.post(f"/api/orders/{order_num}/confirm/")
        self.assertEqual(resp_conf.status_code, status.HTTP_409_CONFLICT)
        err = resp_conf.data["error"]
        self.assertEqual(err["code"], "INSUFFICIENT_STOCK")
        self.assertIn("Insufficient stock for Front Brake Disc", err["message"])
        self.assertEqual(len(err["details"]), 1)
        self.assertEqual(err["details"][0]["sku"], self.p1.sku)
        self.assertEqual(err["details"][0]["available"], 5)
        self.assertEqual(err["details"][0]["requested"], 10)

        # Verify stock was NOT deducted for p2 either (all-or-nothing guarantee!)
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.stock, 5)
        self.assertEqual(self.p2.stock, 2)

    def test_cancellation_and_exact_stock_restoration(self):
        """
        Cancelling a CONFIRMED order restores stock exactly once.
        Cancelling a DRAFT order leaves stock untouched.
        Cancelling an already CANCELLED order is rejected.
        """
        # Case 1: DRAFT cancellation
        r_draft = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 3}]},
            format="json",
        )
        d_num = r_draft.data["order_number"]
        stock_before = self.p1.stock

        r_cancel_draft = self.client.post(f"/api/orders/{d_num}/cancel/")
        self.assertEqual(r_cancel_draft.status_code, status.HTTP_200_OK)
        self.assertEqual(r_cancel_draft.data["status"], "CANCELLED")
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, stock_before)  # Untouched

        # Case 2: CONFIRMED cancellation
        r_conf_order = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 4}]},
            format="json",
        )
        c_num = r_conf_order.data["order_number"]
        self.client.post(f"/api/orders/{c_num}/confirm/")
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, stock_before - 4)

        # Cancel confirmed order
        r_cancel_conf = self.client.post(f"/api/orders/{c_num}/cancel/")
        self.assertEqual(r_cancel_conf.status_code, status.HTTP_200_OK)
        self.assertEqual(r_cancel_conf.data["status"], "CANCELLED")
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, stock_before)  # Restored exactly!

        # Try to cancel again -> 409 INVALID_TRANSITION (cannot restore twice!)
        r_cancel_again = self.client.post(f"/api/orders/{c_num}/cancel/")
        self.assertEqual(r_cancel_again.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r_cancel_again.data["error"]["code"], "INVALID_TRANSITION")
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, stock_before)

    def test_concurrent_confirmations_prevent_overselling(self):
        """
        Simultaneous confirms for the same product must never oversell stock.
        Stock is 5. Two orders each request 4.
        Exactly one must succeed (200), and the other must be rejected (409 INSUFFICIENT_STOCK).
        """
        self.p1.stock = 5
        self.p1.save(update_fields=["stock"])

        # Create two draft orders
        r1 = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 4}]},
            format="json",
        )
        o1 = r1.data["order_number"]

        r2 = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 4}]},
            format="json",
        )
        o2 = r2.data["order_number"]

        def do_confirm(order_num):
            try:
                c = APIClient()
                return c.post(f"/api/orders/{order_num}/confirm/")
            finally:
                connections.close_all()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(do_confirm, o1)
            fut2 = executor.submit(do_confirm, o2)
            res1 = fut1.result()
            res2 = fut2.result()

        statuses = [res1.status_code, res2.status_code]
        self.assertIn(status.HTTP_200_OK, statuses)
        self.assertIn(status.HTTP_409_CONFLICT, statuses)

        self.p1.refresh_from_db()
        # Initial 5 - 4 = 1. Must never be negative!
        self.assertEqual(self.p1.stock, 1)

    def test_concurrent_idempotency_requests(self):
        """
        Multiple concurrent requests with the SAME Idempotency-Key and SAME body
        must create exactly 1 order, and all requests must succeed with the same order_number.
        """
        idem_key = "test-idem-concurrent-123"
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": self.p1.sku, "quantity": 1}],
        }

        def send_order():
            try:
                c = APIClient()
                return c.post(
                    "/api/orders/",
                    payload,
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=idem_key,
                )
            finally:
                connections.close_all()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(send_order) for _ in range(3)]
            results = [f.result() for f in futures]

        for r in results:
            self.assertIn(r.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))

        order_numbers = {r.data["order_number"] for r in results}
        self.assertEqual(len(order_numbers), 1, "Expected identical order_number across all concurrent retries")

        # Database must have exactly 1 record for this key
        self.assertEqual(IdempotencyRecord.objects.filter(key=idem_key).count(), 1)

    def test_idempotency_conflict_with_different_payload(self):
        """Reusing the same key with different body must return 409 IDEMPOTENCY_CONFLICT"""
        idem_key = "test-idem-conflict-456"
        payload1 = {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 1}]}
        payload2 = {"dealer_id": self.dealer.id, "items": [{"sku": self.p1.sku, "quantity": 2}]}

        r1 = self.client.post("/api/orders/", payload1, format="json", HTTP_IDEMPOTENCY_KEY=idem_key)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        r2 = self.client.post("/api/orders/", payload2, format="json", HTTP_IDEMPOTENCY_KEY=idem_key)
        self.assertEqual(r2.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r2.data["error"]["code"], "IDEMPOTENCY_CONFLICT")

    def test_concurrent_order_number_generation(self):
        """Multiple concurrent calls to get_next_order_number must return unique, monotonic order numbers"""
        def get_num():
            try:
                return get_next_order_number()
            finally:
                connections.close_all()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_num) for _ in range(10)]
            numbers = [f.result() for f in futures]

        self.assertEqual(len(numbers), 10)
        self.assertEqual(len(set(numbers)), 10, "Order numbers must be strictly unique")
