import socket
import threading
import time
from decimal import Decimal
from django.test import TransactionTestCase
from django.db import connections
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Product
from core.exceptions import SupplierUnavailableError
from core.services.supplier_sync_service import run_supplier_sync
from supplier_mock.mock_supplier import SupplierMock, serve


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class SupplierSyncTests(TransactionTestCase):
    def setUp(self):
        self.port = get_free_port()
        self.api_url = f"http://127.0.0.1:{self.port}"
        self.api_key = "test-sync-key"
        self.httpd = None

    def tearDown(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        connections.close_all()

    def _start_server(self, mock):
        self.httpd = serve(mock, host="127.0.0.1", port=self.port)
        time.sleep(0.05)

    def test_full_sync_with_rate_limits_transient_failure_and_invalids(self):
        """
        Verify multi-page fetching, 429 rate limit retry with Retry-After,
        500 transient error recovery, and proper invalid item rejection.
        """
        feed = [
            # Page 0 (items 0..19)
            {
                "supplier_sku": "SUP-101",
                "sku": "SYNC-P1",
                "name": "Spark Plug",
                "category": "Electrical",
                "brand": "NGK",
                "vehicle_fitment": "Universal",
                "description": "OEM plug",
                "price": "150.00",
                "supplier_stock": 200,
                "updated_at": "2026-10-06T10:00:00Z",
            },
            {
                "supplier_sku": "SUP-102",
                "sku": "SYNC-P2",
                "name": "Brake Lever",
                "category": "Brakes",
                "brand": "Endurance",
                "vehicle_fitment": "Pulsar 150",
                "description": "Alloy lever",
                "price": "350.50",
                "supplier_stock": 50,
                "updated_at": "2026-10-06T10:00:00Z",
            },
            # Invalid item 1: empty SKU
            {
                "supplier_sku": "SUP-BAD1",
                "sku": "",
                "name": "Mystery Part",
                "category": "Unknown",
                "brand": "Generic",
                "vehicle_fitment": "Universal",
                "description": "Missing sku",
                "price": "100.00",
                "supplier_stock": 10,
                "updated_at": "2026-10-06T10:00:00Z",
            },
            # Invalid item 2: invalid price format
            {
                "supplier_sku": "SUP-BAD2",
                "sku": "SYNC-BAD-PRICE",
                "name": "Defective Price Part",
                "category": "Unknown",
                "brand": "Generic",
                "vehicle_fitment": "Universal",
                "description": "Bad price",
                "price": "N/A",
                "supplier_stock": 10,
                "updated_at": "2026-10-06T10:00:00Z",
            },
            # Invalid item 3: 3 decimal places
            {
                "supplier_sku": "SUP-BAD3",
                "sku": "SYNC-BAD-DEC",
                "name": "Three Decimals Part",
                "category": "Unknown",
                "brand": "Generic",
                "vehicle_fitment": "Universal",
                "description": "Precision error",
                "price": "19.999",
                "supplier_stock": 10,
                "updated_at": "2026-10-06T10:00:00Z",
            },
        ]
        # Pad feed to exceed 20 items so page 1 is created
        for i in range(18):
            feed.append({
                "supplier_sku": f"SUP-PAD-{i}",
                "sku": f"SYNC-PAD-{i}",
                "name": f"Pad Part {i}",
                "category": "Misc",
                "brand": "Generic",
                "vehicle_fitment": "Universal",
                "description": "Filler",
                "price": "50.00",
                "supplier_stock": 100,
                "updated_at": "2026-10-06T10:00:00Z",
            })

        # Configure mock with throttling every 2 requests (429 with 0.1s wait) and page 1 returning 500 once
        mock = SupplierMock(
            feed=feed,
            key=self.api_key,
            throttle_every=2,
            retry_after=1,
            transient={1: [500]},
        )
        self._start_server(mock)

        # Execute sync
        result = run_supplier_sync(
            api_url=self.api_url,
            api_key=self.api_key,
            max_retries=5,
            timeout=5.0,
        )

        self.assertGreaterEqual(result["pages_fetched"], 2)
        self.assertGreater(result["requests_made"], result["pages_fetched"])
        self.assertEqual(len(result["rejected"]), 3)
        rej_reasons = {r["reason"] for r in result["rejected"]}
        self.assertIn("missing sku", rej_reasons)
        self.assertIn("invalid price", rej_reasons)

        # Check created products in database
        self.assertTrue(Product.objects.filter(sku="SYNC-P1").exists())
        p1 = Product.objects.get(sku="SYNC-P1")
        self.assertEqual(p1.name, "Spark Plug")
        self.assertEqual(p1.price, Decimal("150.00"))
        self.assertEqual(p1.stock, 0)  # Created with stock 0!

    def test_idempotent_second_sync(self):
        """A second synchronization on an unchanged feed must make 0 updates and 0 creates."""
        feed = [
            {
                "supplier_sku": "SUP-IDEM-1",
                "sku": "IDEM-01",
                "name": "Handlebar Grip",
                "category": "Accessories",
                "brand": "ProGrip",
                "vehicle_fitment": "Universal",
                "description": "Rubber grip",
                "price": "299.00",
                "supplier_stock": 500,
                "updated_at": "2026-10-06T10:00:00Z",
            }
        ]
        mock = SupplierMock(feed=feed, key=self.api_key)
        self._start_server(mock)

        # First run
        r1 = run_supplier_sync(api_url=self.api_url, api_key=self.api_key)
        self.assertEqual(r1["created"], 1)
        self.assertEqual(r1["updated"], 0)
        self.assertEqual(r1["unchanged"], 0)

        # Second run
        r2 = run_supplier_sync(api_url=self.api_url, api_key=self.api_key)
        self.assertEqual(r2["created"], 0)
        self.assertEqual(r2["updated"], 0)
        self.assertEqual(r2["unchanged"], 1)

    def test_stock_preservation_during_catalogue_update(self):
        """Updating existing catalogue items must NEVER modify local inventory quantity."""
        # Create existing product with stock 77
        Product.objects.create(
            sku="PRESERVE-01",
            name="Air Filter - Old Name",
            category="Filters",
            brand="Bosch",
            vehicle_fitment="Pulsar",
            price=Decimal("200.00"),
            stock=77,
            description="Old description",
        )

        feed = [
            {
                "supplier_sku": "SUP-P-1",
                "sku": "PRESERVE-01",
                "name": "Air Filter - Updated 2026",
                "category": "Filters",
                "brand": "Bosch",
                "vehicle_fitment": "Pulsar 150/180",
                "description": "High airflow",
                "price": "260.00",
                "supplier_stock": 999,  # Supplier has 999
                "updated_at": "2026-10-08T10:00:00Z",
            }
        ]
        mock = SupplierMock(feed=feed, key=self.api_key)
        self._start_server(mock)

        result = run_supplier_sync(api_url=self.api_url, api_key=self.api_key)
        self.assertEqual(result["updated"], 1)

        prod = Product.objects.get(sku="PRESERVE-01")
        self.assertEqual(prod.name, "Air Filter - Updated 2026")
        self.assertEqual(prod.price, Decimal("260.00"))
        self.assertEqual(prod.stock, 77)  # Stock untouched!

    def test_duplicate_skus_resolve_to_latest_updated_at(self):
        """Duplicates across pages must be resolved using the latest updated_at timestamp."""
        feed = [
            # Older version
            {
                "supplier_sku": "SUP-DUP-OLD",
                "sku": "DUP-SKU-01",
                "name": "Clutch Cable (Old)",
                "category": "Cables",
                "brand": "Endurance",
                "vehicle_fitment": "Pulsar",
                "description": "Standard",
                "price": "100.00",
                "supplier_stock": 20,
                "updated_at": "2026-10-06T09:00:00Z",
            },
            # Newer version
            {
                "supplier_sku": "SUP-DUP-NEW",
                "sku": "DUP-SKU-01",
                "name": "Clutch Cable (Latest Heavy Duty)",
                "category": "Cables",
                "brand": "Endurance",
                "vehicle_fitment": "Pulsar 150",
                "description": "Teflon coated",
                "price": "145.00",
                "supplier_stock": 80,
                "updated_at": "2026-10-08T18:00:00Z",
            },
        ]
        mock = SupplierMock(feed=feed, key=self.api_key)
        self._start_server(mock)

        result = run_supplier_sync(api_url=self.api_url, api_key=self.api_key)
        self.assertEqual(result["created"], 1)

        prod = Product.objects.get(sku="DUP-SKU-01")
        self.assertEqual(prod.name, "Clutch Cable (Latest Heavy Duty)")
        self.assertEqual(prod.price, Decimal("145.00"))

    def test_persistent_outage_changes_nothing_and_returns_502(self):
        """
        If a page fails persistently, the sync must abort completely,
        raise SupplierUnavailableError (502), and leave local database untouched.
        """
        # Create baseline product in DB
        Product.objects.create(
            sku="BASELINE-01",
            name="Original Baseline Part",
            category="Misc",
            brand="Original",
            vehicle_fitment="Universal",
            price=Decimal("100.00"),
            stock=10,
            description="Should not change",
        )
        count_before = Product.objects.count()

        feed = [
            # Page 0 (will fetch ok)
            {
                "supplier_sku": f"SUP-P0-{i}",
                "sku": f"OUTAGE-NEW-{i}",
                "name": f"New Part {i}",
                "category": "Misc",
                "brand": "Generic",
                "vehicle_fitment": "Universal",
                "description": "New",
                "price": "75.00",
                "supplier_stock": 10,
                "updated_at": "2026-10-06T10:00:00Z",
            }
            for i in range(25)
        ]

        # Page 1 has persistent outage
        mock = SupplierMock(feed=feed, key=self.api_key, outage_pages=[1])
        self._start_server(mock)

        with self.assertRaises(SupplierUnavailableError) as ctx:
            run_supplier_sync(
                api_url=self.api_url,
                api_key=self.api_key,
                max_retries=2,
                timeout=1.0,
            )

        self.assertEqual(ctx.exception.code, "SUPPLIER_UNAVAILABLE")
        self.assertEqual(ctx.exception.status_code, 502)

        # Crucial: verify 0 new products were committed!
        self.assertEqual(Product.objects.count(), count_before)
        baseline = Product.objects.get(sku="BASELINE-01")
        self.assertEqual(baseline.name, "Original Baseline Part")

    def test_api_endpoint_post_sync_supplier(self):
        """Test POST /api/sync/supplier/ returns 200 with required contract keys."""
        feed = [
            {
                "supplier_sku": "SUP-API-1",
                "sku": "API-SYNC-01",
                "name": "Rear View Mirror",
                "category": "Mirrors",
                "brand": "Uno Minda",
                "vehicle_fitment": "Universal",
                "description": "Convex glass",
                "price": "420.00",
                "supplier_stock": 150,
                "updated_at": "2026-10-06T10:00:00Z",
            }
        ]
        mock = SupplierMock(feed=feed, key=self.api_key)
        self._start_server(mock)

        client = APIClient()
        with self.settings(SUPPLIER_API_URL=self.api_url, SUPPLIER_API_KEY=self.api_key):
            resp = client.post("/api/sync/supplier/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        for k in ("created", "updated", "unchanged", "rejected", "pages_fetched", "requests_made"):
            self.assertIn(k, data)
        self.assertIsInstance(data["rejected"], list)
        self.assertEqual(data["created"], 1)
