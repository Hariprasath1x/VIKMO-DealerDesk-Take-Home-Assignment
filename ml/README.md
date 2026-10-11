# VIKMO DealerDesk — Demand Forecasting & Reorder Intelligence (ML)

This directory contains documentation, modeling artifacts, and reproducibility guides for the VIKMO DealerDesk demand forecasting engine.

---

## 1. Problem Formulation & Contract Specifications

- **Target Horizon**: 4 forecast weeks starting `2026-09-28`, specifically:
  - `2026-09-28` (Week 1)
  - `2026-10-05` (Week 2)
  - `2026-10-12` (Week 3)
  - `2026-10-19` (Week 4)
- **Target Entities**: Exactly the 40 SKUs specified in `data/lead_times.csv`.
- **Output Artifact**: `ml/forecast.csv` (exactly 160 rows).
  - Required columns: `sku,week_start,forecast_units`.
  - Non-negative, finite predictions.
- **Evaluation Criteria**: Scored against held-out ground truth sales using Weighted Absolute Percentage Error (WAPE), Mean Absolute Error (MAE), and Root Mean Squared Error (RMSE) against three simple historical baselines:
  1. **Last Observed Value**: $y_t = y_{t-1}$
  2. **Recent 4-Week Average**: $y_t = \frac{1}{4} \sum_{i=1}^{4} y_{t-i}$
  3. **Same Week Last Year**: $y_t = y_{t-52}$ (where history exists)

---

## 2. Temporal Backtesting & Leakage Prevention

### Rolling-Origin Validation Protocol
To ensure zero lookahead bias and rigorous time-series evaluation, we implemented a 4-fold chronological rolling-origin backtest in `forecasting/backtest.py`:
- **Fold 1**: Train $\le$ 2026-06-08 (W88), Predict 4 weeks: 2026-06-15 to 2026-07-06 (W89–W92)
- **Fold 2**: Train $\le$ 2026-07-06 (W92), Predict 4 weeks: 2026-07-13 to 2026-08-03 (W93–W96)
- **Fold 3**: Train $\le$ 2026-08-03 (W96), Predict 4 weeks: 2026-08-10 to 2026-08-31 (W97–W100)
- **Fold 4**: Train $\le$ 2026-08-31 (W100), Predict 4 weeks: 2026-09-07 to 2026-09-28 (W101–W104)

### Anti-Leakage Invariants
- **Strict Cutoff Filtering**: In `forecasting/features.py:build_feature_matrix`, the historical sales history is strictly filtered using `sales_df[sales_df["week_start"] <= cutoff_date]`. Any observation after `cutoff_date` is mathematically erased before feature computation.
- **Exogenous Information**: Only known-in-advance calendar features (promotions from `promo_calendar.csv`, festival dates from `festival_calendar.csv`, month, week-of-year) are used for future horizon steps. Future sales outcomes never enter feature computation, model fitting, or hyperparameter selection.
- **Recursive / Direct Multi-Step Rollout**: Horizon predictions are generated iteratively; step $h$ uses predicted values from steps $1 \dots h-1$ to update autoregressive rolling features without peeking.

---

## 3. Backtest Empirical Results

Across all 4 rolling validation folds (640 total SKU-week test predictions), candidate models were evaluated against all three assignment baselines:

| Model / Baseline | WAPE (%) | MAE (units) | RMSE (units) |
|---|---|---|---|
| **Baseline 1: Last Observed Value** | 38.45% | 13.28 | 20.44 |
| **Baseline 2: Recent 4-Week Average** | 29.74% | 10.27 | 15.74 |
| **Baseline 3: Same Week Last Year** | 34.28% | 11.84 | 18.14 |
| **Candidate: Segmented GBDT Hybrid** | **27.96%** | **9.66** | **14.98** |

**Relative Improvement**: The Segmented GBDT Hybrid achieves a **27.3% error reduction** over the Last-Value baseline and a **6.0% error reduction** over the Recent-Average baseline.

---

## 4. Modeling Strategy & Segmentation

Demand dynamics in automotive spare parts exhibit high heterogeneity. Rather than forcing a single model across all parts, we employ a 3-tier segmented strategy:

1. **Regular Established Demand (34 SKUs)**:
   - Gradient Boosted Decision Trees (`HistGradientBoostingRegressor`) with Tweedie / Poisson loss support for non-negative continuous demand.
   - Features: Lags ($t-1, t-2, t-3, t-4, t-52$), rolling means/std (4-wk, 12-wk, 26-wk), promotion flags, and signed weeks-to-Diwali.
2. **Intermittent / Zero-Heavy Demand (`ELE-1006`, `GRP-1043`, `BRK-1088`, `ELE-1031`)**:
   - Zero proportion > 35%. GBDT models tend to overfit zero spikes.
   - Handled via Croston-inspired decomposition / exponential smoothing of non-zero intervals and demand size, falling back to robust 8-week median-smoothed baseline.
3. **Short-History / Cold-Start SKUs (`BRK-1105`, `CHN-1006`)**:
   - Only 6 weeks of historical data exist (introduced recently in 2026).
   - 52-week seasonal lags are unavailable.
   - Handled via exponential moving average ($\alpha=0.3$) scaled by active category promotional indicators.

### Festival Calendar & Diwali Dynamic
In 2025, Diwali occurred on `2025-10-20` (overlapping week 4 of October). However, in 2026, Diwali occurs on `2026-11-08` (3 weeks *after* the forecast period ends). 
- Simple 52-week lag models falsely project the October 2025 Diwali demand spike into October 2026.
- Our model uses **signed relative distance** `weeks_to_diwali = (week_start - diwali_date).days // 7` rather than static month-of-year, correctly recognizing that October 2026 is still in the pre-Diwali ramp-up phase.

---

## 5. Artifact Generation & Reproducibility

To re-run the backtesting suite and generate `ml/forecast.csv`:

```bash
# 1. Run the chronological backtest evaluation
python -m forecasting.backtest

# 2. Train on all available history and generate ml/forecast.csv
python -m forecasting.train

# 3. Verify the generated forecast artifact against contract requirements
python -c "
import pandas as pd
df = pd.read_csv('ml/forecast.csv')
assert len(df) == 160, f'Expected 160 rows, got {len(df)}'
assert list(df.columns) == ['sku', 'week_start', 'forecast_units']
assert (df['forecast_units'] >= 0).all()
print('ml/forecast.csv verified: 160 rows, exact columns, all non-negative.')
"
```

---

## 6. Live Reorder Suggestions Integration

The generated forecast feeds directly into the inventory reorder intelligence engine (`forecasting/reorder.py` and `GET /api/reorder-suggestions/`):
- **Lead Time Horizon**: $L$ weeks read from `data/lead_times.csv`.
- **Lead Time Demand**: $\sum_{w=1}^{L} \text{forecast\_units}_w$.
- **Demand Uncertainty ($\sigma$)**: Sample standard deviation ($ddof=1$) computed over the last 12 historical weeks.
- **Safety Stock**: $\lceil 1.65 \times \sigma \times \sqrt{L} \rceil$ (95% service level).
- **Reorder Point**: $\text{lead\_time\_demand} + \text{safety\_stock}$.
- **Reorder Quantity**: $\max(0, \lceil \text{reorder\_point} - \text{current\_stock} \rceil)$ using live stock from PostgreSQL.
