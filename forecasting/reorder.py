import csv
import math
import os
import pandas as pd
from django.conf import settings
from core.models import Product
from forecasting.forecast_service import load_forecast_map

_lead_times_cache = None
_sku_sigma_cache = None


def load_lead_times_and_sigmas():
    global _lead_times_cache, _sku_sigma_cache
    if _lead_times_cache is not None and _sku_sigma_cache is not None:
        return _lead_times_cache, _sku_sigma_cache

    data_dir = getattr(settings, "DATA_DIR", os.path.join(settings.BASE_DIR, "data"))
    lead_path = os.path.join(data_dir, "lead_times.csv")
    sales_path = os.path.join(data_dir, "sales_history.csv")

    lead_map = {}
    with open(lead_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lead_map[r["sku"].strip()] = int(r["lead_time_weeks"].strip())

    sales_df = pd.read_csv(sales_path)
    sales_df["week_start"] = pd.to_datetime(sales_df["week_start"])
    sales_df["units_sold"] = sales_df["units_sold"].astype(float)

    sigma_map = {}
    for sku in lead_map:
        sku_sales = sales_df[sales_df["sku"] == sku].sort_values("week_start")
        # Most recent 12 weeks of sales_history.csv (or all if < 12)
        recent_12 = sku_sales.tail(12)["units_sold"].values
        n = len(recent_12)
        if n > 1:
            # Sample standard deviation (ddof=1)
            sigma = float(pd.Series(recent_12).std(ddof=1))
        else:
            sigma = 0.0
        sigma_map[sku] = sigma

    _lead_times_cache = lead_map
    _sku_sigma_cache = sigma_map
    return _lead_times_cache, _sku_sigma_cache


def calculate_reorder_suggestions() -> list[dict]:
    """
    Computes reorder suggestions for all 40 forecast SKUs based on live PostgreSQL stock
    and contract section 10 formula.
    """
    lead_map, sigma_map = load_lead_times_and_sigmas()
    forecast_map = load_forecast_map()

    # Query live stock from PostgreSQL
    skus = list(lead_map.keys())
    stock_dict = {
        p.sku: p.stock
        for p in Product.objects.filter(sku__in=skus)
    }

    results = []
    for sku, L in lead_map.items():
        current_stock = stock_dict.get(sku, 0)

        # Sum of your forecast_units for the first L forecast weeks
        forecast_entries = forecast_map.get(sku, [])
        lead_time_demand = sum(
            entry["forecast_units"] for entry in forecast_entries[:L]
        )
        lead_time_demand = round(lead_time_demand, 1)

        # Sample standard deviation over the most recent 12 weeks
        sigma = sigma_map.get(sku, 0.0)

        # safety_stock = ceil(1.65 * sigma * sqrt(L))
        safety_stock = int(math.ceil(1.65 * sigma * math.sqrt(L)))

        # reorder_point = lead_time_demand + safety_stock
        reorder_point = round(lead_time_demand + safety_stock, 1)

        # reorder_qty = max(0, ceil(reorder_point - current_stock))
        reorder_qty = max(0, int(math.ceil(reorder_point - current_stock)))

        results.append({
            "sku": sku,
            "current_stock": current_stock,
            "lead_time_weeks": L,
            "lead_time_demand": lead_time_demand,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "reorder_qty": reorder_qty,
        })

    return results
