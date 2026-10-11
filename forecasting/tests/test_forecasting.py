import csv
import math
import os
import pandas as pd
from decimal import Decimal
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Product
from forecasting.features import (
    load_raw_data,
    extract_sku_features_as_of_origin,
)
from forecasting.forecast_service import get_sku_forecast
from forecasting.reorder import calculate_reorder_suggestions

FORECAST_WEEKS = ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]


class ForecastingArtifactTests(TestCase):
    def test_forecast_csv_file_contract(self):
        forecast_path = os.path.join(settings.BASE_DIR, "ml", "forecast.csv")
        self.assertTrue(os.path.exists(forecast_path), "ml/forecast.csv must exist")

        with open(forecast_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 160, "ml/forecast.csv must contain exactly 160 rows")
        self.assertEqual(list(rows[0].keys())[:3], ["sku", "week_start", "forecast_units"])

        # Check all weeks
        seen_weeks = set(r["week_start"] for r in rows)
        self.assertEqual(seen_weeks, set(FORECAST_WEEKS))

        # Check all non-negative numbers
        for r in rows:
            val = float(r["forecast_units"])
            self.assertTrue(val >= 0, f"Negative forecast found: {val}")


class AntiLeakageFeatureTests(TestCase):
    def test_feature_extraction_strictly_respects_cutoff(self):
        sales_df, lead_df, promo_df, fest_df = load_raw_data()
        test_sku = "FIL-1016"
        cutoff_date = pd.Timestamp("2025-09-29")

        features = extract_sku_features_as_of_origin(
            sku=test_sku,
            origin_week=cutoff_date,
            horizon_weeks=1,
            sales_df=sales_df,
            lead_df=lead_df,
            promo_future_df=promo_df,
            fest_df=fest_df,
        )

        # lag_1 must match the units_sold on cutoff_date exactly
        cutoff_sales = sales_df[(sales_df["sku"] == test_sku) & (sales_df["week_start"] == cutoff_date)]
        self.assertEqual(features["lag_1"], float(cutoff_sales["units_sold"].iloc[0]))
        self.assertLessEqual(features["origin_week"], cutoff_date)


class ForecastAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_get_sku_forecast_success(self):
        # FIL-1016 is one of the 40 forecast SKUs
        response = self.client.get("/api/forecast/FIL-1016/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["sku"], "FIL-1016")
        self.assertIn("forecast", data)
        self.assertEqual(len(data["forecast"]), 4)
        week_starts = [entry["week_start"] for entry in data["forecast"]]
        self.assertEqual(week_starts, FORECAST_WEEKS)

    def test_get_sku_forecast_not_found(self):
        response = self.client.get("/api/forecast/NON-EXISTENT-SKU/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        err = response.json()["error"]
        self.assertEqual(err["code"], "NOT_FOUND")


class ReorderAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Seed a test product in the database for stock verification
        Product.objects.update_or_create(
            sku="FIL-1016",
            defaults={
                "name": "Oil Filter - Royal Enfield Classic 350",
                "category": "Filters",
                "brand": "Bosch",
                "vehicle_fitment": "Royal Enfield Classic 350",
                "price": Decimal("250.00"),
                "stock": 40,
            },
        )

    def test_get_reorder_suggestions_schema_and_count(self):
        response = self.client.get("/api/reorder-suggestions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("results", data)
        results = data["results"]
        self.assertEqual(len(results), 40, "Must return suggestions for exactly 40 SKUs")

        required_keys = {
            "sku",
            "current_stock",
            "lead_time_weeks",
            "lead_time_demand",
            "safety_stock",
            "reorder_point",
            "reorder_qty",
        }
        for item in results:
            self.assertTrue(required_keys.issubset(set(item.keys())))

    def test_reorder_formula_mathematical_precision(self):
        suggestions = calculate_reorder_suggestions()
        target_entry = next((s for s in suggestions if s["sku"] == "FIL-1016"), None)
        self.assertIsNotNone(target_entry)

        L = target_entry["lead_time_weeks"]
        lead_time_demand = target_entry["lead_time_demand"]
        safety_stock = target_entry["safety_stock"]
        reorder_point = target_entry["reorder_point"]
        reorder_qty = target_entry["reorder_qty"]
        current_stock = target_entry["current_stock"]

        # 1. reorder_point = lead_time_demand + safety_stock
        self.assertAlmostEqual(reorder_point, lead_time_demand + safety_stock, places=1)

        # 2. reorder_qty = max(0, ceil(reorder_point - current_stock))
        expected_qty = max(0, math.ceil(reorder_point - current_stock))
        self.assertEqual(reorder_qty, expected_qty)

    def test_live_stock_mutation_dynamically_updates_reorder_qty(self):
        # If current stock increases, reorder_qty must drop
        prod = Product.objects.get(sku="FIL-1016")
        initial_stock = prod.stock
        prod.stock = 500  # excessively high stock
        prod.save(update_fields=["stock"])

        response = self.client.get("/api/reorder-suggestions/")
        item = next(s for s in response.json()["results"] if s["sku"] == "FIL-1016")
        self.assertEqual(item["current_stock"], 500)
        self.assertEqual(item["reorder_qty"], 0)

        # Restore original stock
        prod.stock = initial_stock
        prod.save(update_fields=["stock"])
