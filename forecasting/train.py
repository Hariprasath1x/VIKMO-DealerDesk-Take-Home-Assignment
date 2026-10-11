import os
import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from forecasting.features import (
    load_raw_data,
    extract_sku_features_as_of_origin,
)
from forecasting.backtest import FEATURE_COLS

FORECAST_WEEKS = ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]


def train_and_generate_forecast(output_path=None):
    if output_path is None:
        output_path = os.path.join(repo_root, "ml", "forecast.csv")

    sales_df, lead_df, promo_df, fest_df = load_raw_data()
    all_weeks = sorted(sales_df["week_start"].unique())
    target_skus = sorted(lead_df["sku"].unique())

    # Latest historical week in data (origin for forecast)
    origin_week = all_weeks[-1]  # '2026-09-21'
    print(f"Forecasting origin week: {origin_week.strftime('%Y-%m-%d')}")
    print(f"Target forecast weeks: {FORECAST_WEEKS}")
    print(f"Target forecast SKUs: {len(target_skus)}")

    # 1. Build training matrices across historical origin points
    train_feats_by_h = {h: [] for h in range(1, 5)}
    train_targets_by_h = {h: [] for h in range(1, 5)}

    for t_idx in range(12, len(all_weeks) - 4):
        t_orig = all_weeks[t_idx]
        for s in target_skus:
            for h in range(1, 5):
                t_target = t_orig + pd.Timedelta(weeks=h)
                actual_row = sales_df[(sales_df["sku"] == s) & (sales_df["week_start"] == t_target)]
                if actual_row.empty:
                    continue
                feat = extract_sku_features_as_of_origin(
                    s, t_orig, h, sales_df, lead_df, promo_df, fest_df
                )
                train_feats_by_h[h].append([feat[c] for c in FEATURE_COLS])
                train_targets_by_h[h].append(float(actual_row["units_sold"].iloc[0]))

    # 2. Fit direct multi-step models
    models = {}
    for h in range(1, 5):
        X = np.array(train_feats_by_h[h])
        y = np.array(train_targets_by_h[h])
        gbr = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=3,
            random_state=42,
        )
        gbr.fit(X, y)
        models[h] = gbr
        print(f"Trained horizon {h} model on {len(X)} samples.")

    # 3. Generate forecasts for the 4 future target weeks
    forecast_rows = []
    for s in target_skus:
        sku_hist = sales_df[sales_df["sku"] == s].sort_values("week_start")
        is_new_sku = len(sku_hist) < 12
        is_rare_sku = (sku_hist["units_sold"] == 0).mean() > 0.4 if not sku_hist.empty else False

        for h, week_str in enumerate(FORECAST_WEEKS, 1):
            target_ts = pd.Timestamp(week_str)

            if is_new_sku:
                # New SKU: exponential weighted smoothing over available history
                units = sku_hist["units_sold"].values
                weights = np.exp(np.linspace(-1, 0, len(units)))
                weights /= weights.sum()
                base_pred = float(np.sum(units * weights))
                # Check planned promo
                promo_match = promo_df[(promo_df["sku"] == s) & (promo_df["week_start"] == target_ts)]
                if not promo_match.empty and promo_match["promo_flag"].values[0] == 1:
                    base_pred *= 1.25
                forecast_val = round(max(0.0, base_pred), 1)

            elif is_rare_sku:
                # Intermittent: robust recent median/trimmed average
                p_cand = float(sku_hist["units_sold"].tail(12).mean())
                # Check promo
                promo_match = promo_df[(promo_df["sku"] == s) & (promo_df["week_start"] == target_ts)]
                if not promo_match.empty and promo_match["promo_flag"].values[0] == 1:
                    p_cand *= 1.20
                forecast_val = round(max(0.0, p_cand), 1)

            else:
                feat = extract_sku_features_as_of_origin(
                    s, origin_week, h, sales_df, lead_df, promo_df, fest_df
                )
                x_feat = np.array([[feat[c] for c in FEATURE_COLS]])
                pred = float(models[h].predict(x_feat)[0])
                forecast_val = round(max(0.0, pred), 1)

            forecast_rows.append({
                "sku": s,
                "week_start": week_str,
                "forecast_units": forecast_val,
            })

    forecast_df = pd.DataFrame(forecast_rows)
    # Ensure correct column order: sku,week_start,forecast_units
    forecast_df = forecast_df[["sku", "week_start", "forecast_units"]]

    # Validate output
    assert len(forecast_df) == 160, f"Expected 160 rows, got {len(forecast_df)}"
    assert set(forecast_df.columns) == {"sku", "week_start", "forecast_units"}
    assert (forecast_df["forecast_units"] >= 0).all(), "Found negative forecast units!"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    forecast_df.to_csv(output_path, index=False)
    print(f"Successfully generated and verified {output_path} with {len(forecast_df)} rows.")
    return forecast_df


if __name__ == "__main__":
    train_and_generate_forecast()
