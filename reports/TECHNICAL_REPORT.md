# Volve Production Forecasting (DCA) with Operational Emissions Proxy and Scenario Analysis

**Author:** Abu Mohammad Taief  
**Date:** January 2026  
**Target role:** Equinor North Development Program 2026 — Engineer Reservoir Technology (Harstad)

---

## Memo (1 page)

### Problem
Reservoir engineers need short/medium-term production forecasts that are transparent, validated, and useful for decisions such as rate constraints and emissions planning.

### What I built
Using Equinor’s public Volve dataset, I built a reproducible workflow from raw daily wellbore data to:

- quality-controlled time series (explicit handling of downtime/shut-ins)
- a decline-curve baseline forecast (exponential vs hyperbolic)
- time-based backtesting metrics
- an operational CO₂ proxy (Scope 1+2 intensity-based) and a simple rate-cap scenario comparison

### Why it’s defendable
- **Operational effects are handled explicitly**: zeros are often downtime, not reservoir behavior.
- **Validation uses time split** (train on early period, test on last 90 flowing days), not random sampling.

### Data provenance (exactly what was used)
- **Source file:** `Volve production data.xlsx` (sheet: **Daily Production Data**)
- **Raw columns used (rates + operations):** `DATEPRD`, `WELL_BORE_CODE`, `ON_STREAM_HRS`, `BORE_OIL_VOL`, `BORE_GAS_VOL`, `BORE_WAT_VOL`, `AVG_WHP_P`, `AVG_DOWNHOLE_PRESSURE`, `AVG_CHOKE_SIZE_P`, `DP_CHOKE_SIZE`, `BORE_WI_VOL`, `FLOW_KIND`, `WELL_TYPE`
- **Processed dataset:** `data/processed/volve_daily.csv`
- **Coverage:** 7 wellbores, daily data (2007–2016)

### Core idea: separate “production decline” from “downtime”
Shut-ins/downtime produce zeros that should not be fitted by a decline curve. Therefore, DCA is fitted on **flowing days only**:

- `on_stream_hrs > 0`
- oil rate > 0

To reduce the mixing of downtime with rate behavior, I compute an uptime-corrected effective flowing rate:

\[
q_{oil,eff} = \frac{q_{oil}}{\max(on\_stream\_hrs,\epsilon)/24}
\]

**Numeric example:** if a well produces 240 Sm³ in a day but flowed only 6 hours, the effective flowing rate is roughly 240 / (6/24) = 960 Sm³/d.

---

## Technical details (3 pages)

## 1) Dataset and processing
Processing steps were kept intentionally simple and auditable:

1. Parse dates and sort per wellbore.
2. Clamp `on_stream_hrs` to [0, 24].
3. Remove negative rates (treated as invalid corrections).
4. Compute effective flowing rates `q_*_eff`.
5. Aggregate duplicates on (well, date) if present.

## 2) Forecasting method: Decline Curve Analysis (DCA)
DCA is a widely used reservoir-engineering baseline for production decline forecasting.

Models fitted:

- **Exponential:** \( q(t) = q_i e^{-Dt} \)
- **Hyperbolic:** \( q(t) = q_i (1 + b D_i t)^{-1/b} \)

**Model selection:** AIC (Akaike Information Criterion) to balance fit quality vs complexity.

**Training data:** flowing days only (uptime > 0 and production > 0).

## 3) Validation: time-based train/test split
To mimic real forecasting, the evaluation is done on time:

- **Train:** all flowing-day observations up to 90 days before end
- **Test:** last 90 flowing-day observations

## 4) Metrics (kept minimal and defensible)
We keep metrics simple and interview-friendly (engineering units):

- **MAE:** mean |y − ŷ| in Sm³/d.
- **RMSE:** like MAE but penalizes large misses more strongly.

Evaluation is done with a **time-based split** (last 90 flowing days held out).

## 5) Operational CO₂ proxy (Scope 1+2)
The job description mentions “emission predictions.” Without metered facility emissions, this project uses an **intensity-based proxy**.

Assumption used for Volve (small mature FPSO field):
- **70 kg CO₂ per Sm³ oil** (operational emissions only: power generation, flaring, fugitive)

This is a proxy, not reporting-grade emissions.

## 6) Scenario analysis (decision support)
To avoid a non-binding cap, the rate cap is **data-derived**:

- compute P95 of historical daily rates
- apply cap = 0.8 × P95
- compare cumulative oil and operational CO₂

---

## Results

### Backtest performance across wells (q_oil_eff)
| Wellbore | Model | RMSE (Sm³/d) | MAE (Sm³/d) | AIC |
|----------|-------|--------------|-------------|-----|
| NO 15/9-F-15 D | Hyperbolic | 34.8 | 28.7 | 5524 |
| NO 15/9-F-1 C | Hyperbolic | 84.5 | 69.3 | 3800 |
| NO 15/9-F-12 H | Exponential | 134.3 | 132.1 | 37776 |
| NO 15/9-F-14 H | Exponential | 208.8 | 208.6 | 32499 |
| NO 15/9-F-11 H | Exponential | 510.0 | 508.7 | 12058 |

**Interpretation:** some wells are well-described by a simple DCA baseline (e.g., F-15 D), while others show operational regime changes where **pressure/choke/injection signals** help explain deviations.

## 7) Operational signals (pressure, choke, injection): why they matter for DCA
Volve provides operational signals that help explain rate changes that are not purely “reservoir decline”:

- **Choke** (`AVG_CHOKE_SIZE_P`, `DP_CHOKE_SIZE`): choke adjustments directly change rate and can create step changes that DCA will not predict.
- **Pressure** (`AVG_WHP_P`, `AVG_DOWNHOLE_PRESSURE`): pressure depletion/support changes the producing drawdown and therefore the decline behavior.
- **Injection** (`BORE_WI_VOL`) + **well role** (`FLOW_KIND`, `WELL_TYPE`): producer vs injector behavior differs; injection activity can support pressure and stabilize rate.

In the dashboard, these signals are plotted as time series and as scatter vs oil rate to make operational regime changes visible and interview-defensible.

### Showcase well: NO 15/9-F-14 H
- **Flowing days used:** 2723 (2008-07-13 to 2016-07-13)
- **Cumulative oil (flowing days, q_oil_eff):** 4,109,499 Sm³
- **Cumulative operational CO₂ proxy:** 287,665 tonnes (70 kg CO₂/Sm³)

### Scenario: cap = 0.8 × P95 (showcase well)
- **P95:** 4,225 Sm³/d → **cap:** 3,380 Sm³/d
- **Base cumulative oil:** 4,109,499 Sm³
- **Capped cumulative oil:** 3,863,906 Sm³ (94.0% of base; Δ = 245,592 Sm³)
- **Base operational CO₂:** 287,665 tonnes
- **Capped operational CO₂:** 270,473 tonnes

---

## Limitations (explicit)
- DCA is empirical and single-well; it does not represent full reservoir physics.
- Emissions are an intensity-based proxy; metered emissions would be required for reporting-grade estimates.

## Next steps (if given access to richer Equinor data)
- include choke/pressure/injection signals
- segment by regime changes (workovers, water breakthrough)
- compare DCA to a data-driven baseline
- align emissions estimation with Equinor reporting methodology

---

## Figures and deliverables
- LaTeX report (Overleaf): `reports/TECHNICAL_REPORT.tex`
- Figures: `reports/figures/`
- Dashboard: `app/streamlit_app.py`

