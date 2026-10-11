import csv
import os
from django.conf import settings

_forecast_cache = None


def load_forecast_map():
    global _forecast_cache
    if _forecast_cache is not None:
        return _forecast_cache

    forecast_file = getattr(
        settings,
        "FORECAST_FILE_PATH",
        os.path.join(settings.BASE_DIR, "ml", "forecast.csv"),
    )

    if not os.path.exists(forecast_file):
        return {}

    mapping = {}
    with open(forecast_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row["sku"].strip()
            w_start = row["week_start"].strip()
            units = float(row["forecast_units"].strip())

            if sku not in mapping:
                mapping[sku] = []
            mapping[sku].append({
                "week_start": w_start,
                "forecast_units": units,
            })

    # Sort each SKU's forecast by week_start
    for sku in mapping:
        mapping[sku].sort(key=lambda x: x["week_start"])

    _forecast_cache = mapping
    return _forecast_cache


def get_sku_forecast(sku: str) -> dict | None:
    f_map = load_forecast_map()
    if sku not in f_map:
        return None
    return {
        "sku": sku,
        "forecast": f_map[sku],
    }


def reload_forecast_cache():
    global _forecast_cache
    _forecast_cache = None
    return load_forecast_map()
