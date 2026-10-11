import os
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
try:
    from django.conf import settings
    if settings.configured:
        DATA_DIR = getattr(settings, "DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
    else:
        DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
except Exception:
    DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def load_raw_data(data_dir=None):
    if data_dir is None:
        data_dir = DATA_DIR

    sales_path = os.path.join(data_dir, "sales_history.csv")
    lead_path = os.path.join(data_dir, "lead_times.csv")
    promo_path = os.path.join(data_dir, "promo_calendar.csv")
    fest_path = os.path.join(data_dir, "festival_calendar.csv")

    sales_df = pd.read_csv(sales_path)
    sales_df["week_start"] = pd.to_datetime(sales_df["week_start"])
    sales_df["units_sold"] = sales_df["units_sold"].astype(float)
    sales_df["promo_flag"] = sales_df["promo_flag"].astype(int)

    lead_df = pd.read_csv(lead_path)
    lead_df["lead_time_weeks"] = lead_df["lead_time_weeks"].astype(int)

    promo_df = pd.read_csv(promo_path)
    promo_df["week_start"] = pd.to_datetime(promo_df["week_start"])
    promo_df["promo_flag"] = promo_df["promo_flag"].astype(int)

    fest_df = pd.read_csv(fest_path)
    fest_df["date"] = pd.to_datetime(fest_df["date"])

    return sales_df, lead_df, promo_df, fest_df


def get_diwali_proximity_weeks(week_date: pd.Timestamp, fest_df: pd.DataFrame) -> float:
    """
    Computes signed difference in weeks to the closest Diwali date.
    Negative = weeks before Diwali, Positive = weeks after Diwali.
    """
    diwali_dates = fest_df[fest_df["festival"] == "Diwali"]["date"].values
    min_diff_weeks = 999.0
    for d_date in diwali_dates:
        d_ts = pd.to_datetime(d_date)
        diff_days = (week_date - d_ts).days
        diff_weeks = diff_days / 7.0
        if abs(diff_weeks) < abs(min_diff_weeks):
            min_diff_weeks = diff_weeks
    return float(min_diff_weeks)


def extract_sku_features_as_of_origin(
    sku: str,
    origin_week: pd.Timestamp,
    horizon_weeks: int,
    sales_df: pd.DataFrame,
    lead_df: pd.DataFrame,
    promo_future_df: pd.DataFrame,
    fest_df: pd.DataFrame,
) -> dict:
    """
    Computes feature vector for predicting week (origin_week + horizon_weeks).
    STRICT ANTI-LEAKAGE GUARANTEE:
    Only observations with week_start <= origin_week are used.
    """
    history = sales_df[(sales_df["sku"] == sku) & (sales_df["week_start"] <= origin_week)].sort_values("week_start")
    target_week = origin_week + pd.Timedelta(weeks=horizon_weeks)

    lead_row = lead_df[lead_df["sku"] == sku]
    lead_time = int(lead_row["lead_time_weeks"].values[0]) if not lead_row.empty else 2

    # Promo flag for the target future week (known in advance)
    target_promo_match = promo_future_df[
        (promo_future_df["sku"] == sku) & (promo_future_df["week_start"] == target_week)
    ]
    if not target_promo_match.empty:
        future_promo = int(target_promo_match["promo_flag"].values[0])
    else:
        future_promo = 0

    if history.empty:
        return {
            "sku": sku,
            "origin_week": origin_week,
            "target_week": target_week,
            "horizon": horizon_weeks,
            "lag_1": 0.0,
            "lag_2": 0.0,
            "lag_3": 0.0,
            "lag_4": 0.0,
            "lag_52": 0.0,
            "rolling_mean_4": 0.0,
            "rolling_std_4": 0.0,
            "rolling_mean_12": 0.0,
            "rolling_std_12": 0.0,
            "promo_future": future_promo,
            "promo_lag_1": 0,
            "weeks_to_diwali": get_diwali_proximity_weeks(target_week, fest_df),
            "lead_time": lead_time,
            "n_history": 0,
            "zero_rate": 0.0,
        }

    units = history["units_sold"].values
    promos = history["promo_flag"].values
    n = len(units)

    lag_1 = float(units[-1])
    lag_2 = float(units[-2]) if n >= 2 else lag_1
    lag_3 = float(units[-3]) if n >= 3 else lag_2
    lag_4 = float(units[-4]) if n >= 4 else lag_3

    # Lag 52 (same week last year)
    lag_52 = float(units[-52]) if n >= 52 else float(np.mean(units[-min(12, n):]))

    # Rolling statistics
    window_4 = units[-min(4, n):]
    rolling_mean_4 = float(np.mean(window_4))
    rolling_std_4 = float(np.std(window_4, ddof=1)) if len(window_4) > 1 else 0.0

    window_12 = units[-min(12, n):]
    rolling_mean_12 = float(np.mean(window_12))
    rolling_std_12 = float(np.std(window_12, ddof=1)) if len(window_12) > 1 else 0.0

    zero_rate = float(np.mean(units == 0))

    return {
        "sku": sku,
        "origin_week": origin_week,
        "target_week": target_week,
        "horizon": horizon_weeks,
        "lag_1": lag_1,
        "lag_2": lag_2,
        "lag_3": lag_3,
        "lag_4": lag_4,
        "lag_52": lag_52,
        "rolling_mean_4": rolling_mean_4,
        "rolling_std_4": rolling_std_4,
        "rolling_mean_12": rolling_mean_12,
        "rolling_std_12": rolling_std_12,
        "promo_future": future_promo,
        "promo_lag_1": int(promos[-1]),
        "weeks_to_diwali": get_diwali_proximity_weeks(target_week, fest_df),
        "lead_time": lead_time,
        "n_history": n,
        "zero_rate": zero_rate,
    }
