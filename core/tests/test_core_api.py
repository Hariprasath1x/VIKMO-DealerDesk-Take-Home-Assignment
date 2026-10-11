import re
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Product, Dealer, Order, OrderItem
from core.services.pricing_service import calculate_line, calculate_order_totals

MONEY_REGEX = re.compile(r"^-?\d+\.\d{2}$")
ORDER_NUMBER_REGEX = re.compile(r"^ORD-\d{8}-\d{4}$")


class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})


class ProductAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = Product.objects.create(
            sku="TST-1001",
            name="Test Brake Pad",
            category="Brakes",
            brand="Brembo",
            vehicle_fitment="KTM Duke 390",
            price=Decimal("1500.00"),
            stock=50,
            description="High performance brakes",
        )

    def test_list_products_pagination_and_format(self):
        response = self.client.get("/api/products/?page_size=5")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertTrue(len(data["results"]) >= 1)
        item = data["results"][0]
        self.assertTrue(MONEY_REGEX.match(item["price"]))
        self.assertIsInstance(item["stock"], int)

    def test_filter_products(self):
        # Search filter
        resp_search = self.client.get("/api/products/?search=brembo")
        self.assertEqual(resp_search.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_search.json()["count"], 1)

        # Category filter
        resp_cat = self.client.get("/api/products/?category=Brakes")
        self.assertEqual(resp_cat.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_cat.json()["count"], 1)

        # Vehicle filter
        resp_veh = self.client.get("/api/products/?vehicle=Duke")
        self.assertEqual(resp_veh.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_veh.json()["count"], 1)

    def test_get_product_detail(self):
        response = self.client.get(f"/api/products/{self.product.sku}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["sku"], self.product.sku)
        self.assertEqual(data["price"], "1500.00")
        self.assertEqual(data["stock"], 50)

    def test_get_product_not_found(self):
        response = self.client.get("/api/products/NON-EXISTENT/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        err = response.json()["error"]
        self.assertEqual(err["code"], "NOT_FOUND")

    def test_create_product(self):
        payload = {
            "sku": "NEW-2002",
            "name": "New Spark Plug",
            "category": "Lighting & Electrical",
            "brand": "NGK",
            "vehicle_fitment": "Universal",
            "price": "299.50",
            "description": "Standard plug",
        }
        response = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["sku"], "NEW-2002")
        self.assertEqual(data["stock"], 0)
        self.assertEqual(data["price"], "299.50")

    def test_create_duplicate_product(self):
        payload = {
            "sku": self.product.sku,
            "name": "Duplicate Item",
            "category": "Brakes",
            "brand": "Brembo",
            "vehicle_fitment": "Universal",
            "price": "500.00",
            "description": "dup",
        }
        response = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        err = response.json()["error"]
        self.assertEqual(err["code"], "DUPLICATE")

    def test_create_invalid_price(self):
        payload = {
            "sku": "BAD-PRICE",
            "name": "Bad Price Item",
            "category": "Brakes",
            "brand": "Brembo",
            "vehicle_fitment": "Universal",
            "price": "-10.00",
            "description": "bad",
        }
        response = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        err = response.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_patch_product(self):
        response = self.client.patch(
            f"/api/products/{self.product.sku}/",
            {"price": "1650.75"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["price"], "1650.75")


class InventoryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = Product.objects.create(
            sku="INV-1001",
            name="Stock Test Product",
            category="Filters",
            brand="K&N",
            vehicle_fitment="Universal",
            price=Decimal("1200.00"),
            stock=10,
        )

    def test_update_inventory_success(self):
        response = self.client.put(
            f"/api/inventory/{self.product.sku}/",
            {"quantity": 42, "reason": "physical audit"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["sku"], self.product.sku)
        self.assertEqual(data["quantity"], 42)

        # Verify reflected in product detail
        prod_resp = self.client.get(f"/api/products/{self.product.sku}/")
        self.assertEqual(prod_resp.json()["stock"], 42)

    def test_update_inventory_negative_quantity(self):
        response = self.client.put(
            f"/api/inventory/{self.product.sku}/",
            {"quantity": -5, "reason": "wrong count"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        err = response.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_update_inventory_unknown_sku(self):
        response = self.client.put(
            "/api/inventory/UNKNOWN-SKU/",
            {"quantity": 10, "reason": "missing"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        err = response.json()["error"]
        self.assertEqual(err["code"], "NOT_FOUND")


class DealerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-099",
            name="Bengaluru Superbike Spares",
            city="Bengaluru",
            phone="9876543210",
            email="spares@example.com",
            gstin="29ABCDE1234F1Z5",
            credit_limit=Decimal("150000.00"),
        )

    def test_list_dealers(self):
        response = self.client.get("/api/dealers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertEqual(data["results"][0]["dealer_code"], self.dealer.dealer_code)
        self.assertTrue(MONEY_REGEX.match(data["results"][0]["credit_limit"]))

    def test_create_dealer(self):
        payload = {
            "dealer_code": "DLR-100",
            "name": "Mysuru Motors",
            "city": "Mysuru",
        }
        response = self.client.post("/api/dealers/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["dealer_code"], "DLR-100")
        self.assertIn("id", data)

    def test_create_duplicate_dealer(self):
        payload = {
            "dealer_code": self.dealer.dealer_code,
            "name": "Another Store",
        }
        response = self.client.post("/api/dealers/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        err = response.json()["error"]
        self.assertEqual(err["code"], "DUPLICATE")

    def test_get_dealer_detail(self):
        response = self.client.get(f"/api/dealers/{self.dealer.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["dealer_code"], self.dealer.dealer_code)

    def test_get_dealer_not_found(self):
        response = self.client.get("/api/dealers/999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        err = response.json()["error"]
        self.assertEqual(err["code"], "NOT_FOUND")


class OrderAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-001",
            name="First Dealer",
            credit_limit=Decimal("50000.00"),
        )
        self.product1 = Product.objects.create(
            sku="BRK-1044",
            name="Brake Pad Set - Bajaj Pulsar 150",
            category="Brakes",
            brand="Endurance",
            vehicle_fitment="Bajaj Pulsar 150",
            price=Decimal("1459.50"),
            stock=100,
        )
        self.product2 = Product.objects.create(
            sku="FIL-1001",
            name="Oil Filter - Pulsar",
            category="Filters",
            brand="Bosch",
            vehicle_fitment="Bajaj Pulsar 150",
            price=Decimal("200.00"),
            stock=50,
        )

    def test_create_draft_order_exact_financial_calculation(self):
        # 3 units of BRK-1044 @ 1459.50 = 4378.50 subtotal
        # tax = 4378.50 * 0.18 = 788.13
        # total = 5166.63
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "BRK-1044", "quantity": 3}],
        }
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertTrue(ORDER_NUMBER_REGEX.match(data["order_number"]))
        self.assertEqual(data["status"], "DRAFT")
        self.assertEqual(data["dealer_id"], self.dealer.id)
        self.assertEqual(data["subtotal"], "4378.50")
        self.assertEqual(data["tax_total"], "788.13")
        self.assertEqual(data["grand_total"], "5166.63")

        item = data["items"][0]
        self.assertEqual(item["sku"], "BRK-1044")
        self.assertEqual(item["unit_price"], "1459.50")
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(item["line_subtotal"], "4378.50")
        self.assertEqual(item["line_tax"], "788.13")
        self.assertEqual(item["line_total"], "5166.63")

    def test_create_order_empty_items(self):
        payload = {"dealer_id": self.dealer.id, "items": []}
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        err = response.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_create_order_duplicate_sku_in_items(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [
                {"sku": "BRK-1044", "quantity": 2},
                {"sku": "BRK-1044", "quantity": 1},
            ],
        }
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        err = response.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_create_order_unknown_sku(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "NON-EXISTENT", "quantity": 1}],
        }
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        err = response.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_create_order_invalid_quantity(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "BRK-1044", "quantity": 0}],
        }
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        err = response.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_idempotency_key_behavior(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "BRK-1044", "quantity": 1}],
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "test-key-12345"}

        # First request
        resp1 = self.client.post("/api/orders/", payload, format="json", **headers)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        order_num = resp1.json()["order_number"]

        # Duplicate request with same body -> returns original order
        resp2 = self.client.post("/api/orders/", payload, format="json", **headers)
        self.assertIn(resp2.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertEqual(resp2.json()["order_number"], order_num)

        # Reused key with DIFFERENT body -> 409 IDEMPOTENCY_CONFLICT
        different_payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "FIL-1001", "quantity": 5}],
        }
        resp3 = self.client.post("/api/orders/", different_payload, format="json", **headers)
        self.assertEqual(resp3.status_code, status.HTTP_409_CONFLICT)
        err = resp3.json()["error"]
        self.assertEqual(err["code"], "IDEMPOTENCY_CONFLICT")

    def test_order_detail_view(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "BRK-1044", "quantity": 1}],
        }
        create_resp = self.client.post("/api/orders/", payload, format="json")
        order_num = create_resp.json()["order_number"]

        detail_resp = self.client.get(f"/api/orders/{order_num}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.json()["order_number"], order_num)
