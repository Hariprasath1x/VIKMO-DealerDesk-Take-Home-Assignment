import math
import os
import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from forecasting.features import load_raw_data, extract_sku_features_as_of_origin

FEATURE_COLS = [
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_4",
    "lag_52",
    "rolling_mean_4",
    "rolling_std_4",
    "rolling_mean_12",
    "rolling_std_12",
    "promo_future",
    "promo_lag_1",
    "weeks_to_diwali",
    "lead_time",
    "zero_rate",
]


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Computes WAPE, MAE, and RMSE.
    Avoids division by zero using total sum denominator for WAPE.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.maximum(0.0, np.asarray(y_pred, dtype=float))  # clip >= 0

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    sum_actual = float(np.sum(y_true))
    wape = float(np.sum(np.abs(y_true - y_pred)) / sum_actual) if sum_actual > 0 else 0.0

    return {
        "MAE": round(mae, 3),
        "RMSE": round(rmse, 3),
        "WAPE%": round(wape * 100.0, 2),
    }


def predict_baseline_last_value(sku, origin_week, horizon, sales_df):
    history = sales_df[(sales_df["sku"] == sku) & (sales_df["week_start"] <= origin_week)].sort_values("week_start")
    if history.empty:
        return 0.0
    return float(history["units_sold"].iloc[-1])


def predict_baseline_recent_avg(sku, origin_week, horizon, sales_df):
    history = sales_df[(sales_df["sku"] == sku) & (sales_df["week_start"] <= origin_week)].sort_values("week_start")
    if history.empty:
        return 0.0
    recent = history["units_sold"].tail(4)
    return float(np.mean(recent))


def predict_baseline_same_week_last_year(sku, origin_week, horizon, sales_df):
    target_week = origin_week + pd.Timedelta(weeks=horizon)
    target_last_year = target_week - pd.Timedelta(weeks=52)
    match = sales_df[(sales_df["sku"] == sku) & (sales_df["week_start"] == target_last_year)]
    if not match.empty:
        return float(match["units_sold"].iloc[0])
    return predict_baseline_recent_avg(sku, origin_week, horizon, sales_df)


def run_rolling_backtest(n_origins: int = 4):
    """
    Executes chronological rolling-origin backtesting over the last n_origins periods.
    Compares:
      1. Baseline: Last Value
      2. Baseline: Recent 4-Week Average
      3. Baseline: Same Week Last Year
      4. Candidate Strategy: Segmented Gradient Boosting Regressor + Specialized Handlers
    """
    sales_df, lead_df, promo_df, fest_df = load_raw_data()
    all_weeks = sorted(sales_df["week_start"].unique())
    target_skus = sorted(lead_df["sku"].unique())

    # We test 4-week forecast windows starting at distinct historical origins
    # History length is 104 weeks. Origins at week indices: -16, -12, -8, -4
    origins = [all_weeks[-4 * i - 4] for i in range(n_origins, 0, -1)]

    records_true = []
    records_last = []
    records_recent = []
    records_samesun = []
    records_candidate = []

    print(f"Running rolling-origin validation across {len(origins)} cutoff origins...")

    for fold_idx, origin_week in enumerate(origins, 1):
        origin_ts = pd.Timestamp(origin_week)
        val_weeks = [origin_ts + pd.Timedelta(weeks=h) for h in range(1, 5)]

        # Build training set strictly before origin_week
        # Construct sample pairs (t_prev, target_t_prev + h)
        train_feats = []
        train_targets = {h: [] for h in range(1, 5)}
        train_feats_by_h = {h: [] for h in range(1, 5)}

        hist_weeks = [w for w in all_weeks if w <= origin_ts]
        # Train on past slices with at least 12 weeks of warmup
        for t_idx in range(12, len(hist_weeks) - 4):
            t_orig = hist_weeks[t_idx]
            for s in target_skus:
                for h in range(1, 5):
                    t_target = t_orig + pd.Timedelta(weeks=h)
                    target_row = sales_df[(sales_df["sku"] == s) & (sales_df["week_start"] == t_target)]
                    if target_row.empty:
                        continue
                    feat = extract_sku_features_as_of_origin(
                        s, t_orig, h, sales_df, lead_df, promo_df, fest_df
                    )
                    train_feats_by_h[h].append([feat[c] for c in FEATURE_COLS])
                    train_targets[h].append(float(target_row["units_sold"].iloc[0]))

        # Fit direct multi-step models for each horizon
        models = {}
        for h in range(1, 5):
            X = np.array(train_feats_by_h[h])
            y = np.array(train_targets[h])
            if len(X) > 0:
                gbr = GradientBoostingRegressor(
                    n_estimators=80,
                    learning_rate=0.06,
                    max_depth=3,
                    random_state=42,
                )
                gbr.fit(X, y)
                models[h] = gbr

        # Evaluate on the 4 out-of-sample validation weeks
        for s in target_skus:
            # Check SKU history availability at origin
            sku_hist = sales_df[(sales_df["sku"] == s) & (sales_df["week_start"] <= origin_ts)]
            is_new_sku = len(sku_hist) < 12
            is_rare_sku = (sku_hist["units_sold"] == 0).mean() > 0.4 if not sku_hist.empty else False

            for h in range(1, 5):
                target_w = origin_ts + pd.Timedelta(weeks=h)
                actual_row = sales_df[(sales_df["sku"] == s) & (sales_df["week_start"] == target_w)]
                if actual_row.empty:
                    continue
                actual_val = float(actual_row["units_sold"].iloc[0])

                # Baselines
                p_last = predict_baseline_last_value(s, origin_ts, h, sales_df)
                p_recent = predict_baseline_recent_avg(s, origin_ts, h, sales_df)
                p_samesun = predict_baseline_same_week_last_year(s, origin_ts, h, sales_df)

                # Candidate Strategy
                if is_new_sku:
                    # New SKU: Exponential weighted moving average
                    units_arr = sku_hist["units_sold"].values
                    weights = np.exp(np.linspace(-1, 0, len(units_arr)))
                    weights /= weights.sum()
                    p_cand = float(np.sum(units_arr * weights))
                elif is_rare_sku:
                    # Intermittent: recent median/truncated average
                    p_cand = float(sku_hist["units_sold"].tail(8).mean())
                elif h in models:
                    feat = extract_sku_features_as_of_origin(s, origin_ts, h, sales_df, lead_df, promo_df, fest_df)
                    x_feat = np.array([[feat[c] for c in FEATURE_COLS]])
                    p_cand = max(0.0, float(models[h].predict(x_feat)[0]))
                else:
                    p_cand = p_recent

                records_true.append(actual_val)
                records_last.append(p_last)
                records_recent.append(p_recent)
                records_samesun.append(p_samesun)
                records_candidate.append(p_cand)

    # Compute aggregate metrics
    y_true = np.array(records_true)
    results = {
        "Baseline: Last Value": evaluate_predictions(y_true, np.array(records_last)),
        "Baseline: Recent 4-Week Average": evaluate_predictions(y_true, np.array(records_recent)),
        "Baseline: Same Week Last Year": evaluate_predictions(y_true, np.array(records_samesun)),
        "Candidate: Segmented GBDT Hybrid": evaluate_predictions(y_true, np.array(records_candidate)),
    }

    print("=" * 65)
    print("CHRONOLOGICAL BACKTEST BENCHMARK RESULTS (Across All Validation Folds)")
    print("=" * 65)
    for model_name, metrics in results.items():
        print(f"{model_name:<35} | WAPE: {metrics['WAPE%']:>5.2f}% | MAE: {metrics['MAE']:>5.2f} | RMSE: {metrics['RMSE']:>5.2f}")
    print("=" * 65)

    return results


if __name__ == "__main__":
    run_rolling_backtest()
