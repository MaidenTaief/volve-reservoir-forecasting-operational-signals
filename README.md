# Volve Reservoir Forecasting (Equinor interview project)

This repo is a **small but defensible** technical showcase for the Equinor Reservoir Engineer posting (Harstad). It uses **real Equinor Volve production data** and focuses on what reservoir teams actually do: QC → forecasting baseline → validation → decision-support style scenario → emissions proxy (clearly documented assumptions).

## What’s inside

- **Data processing**: Excel → clean daily wellbore time series
- **QC**: downtime/shut-ins and uptime-corrected rates
- **Forecasting baseline**: DCA (exponential vs hyperbolic) + AIC selection
- **Validation**: time-based backtest (last 90 flowing days held out)
- **Emissions proxy**: operational CO₂ intensity proxy (Scope 1+2) with explicit assumptions
- **Scenario**: data-derived rate cap (0.8×P95) to show trade-offs
- **Dashboard**: Streamlit app to present results clearly
- **Report**: Overleaf-ready LaTeX + readable Markdown

## Setup (recommended)

```bash
cd "/Users/taief/Desktop/Norway Dam/equinor"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Data

Put the Volve Excel file here:

- `data/raw/Volve production data.xlsx`

Then preprocess:

```bash
python scripts/preprocess_volve.py --input data/raw --output data/processed/volve_daily.csv
```

Note: this repo does **not** commit the raw dataset. Download it from Kaggle and place it under `data/raw/`:
- `https://www.kaggle.com/datasets/lamyalbert/volve-production-data`

Parquet is optional; if a Parquet engine isn’t available, the script can fall back to CSV.

## Run the dashboard (localhost)

```bash
.venv/bin/streamlit run app/streamlit_app.py
```

Open: `http://localhost:8501`

## What to look at (one paragraph)
In the Streamlit dashboard, pick a well (default **NO 15/9-F-14 H**) and start from downtime: spikes in downtime indicate shut-ins/operational stops, so zeros should not be treated as reservoir decline. Switch to the **effective (uptime-corrected)** oil rate to see decline behavior more clearly, then review the **DCA fit** and **DCA backtest** (train on history, test on last 90 flowing days) along with **RMSE/MAE** in Sm³/d. Finally, check **Operational signals** (pressure/choke/injection) to see regime changes that can explain DCA deviations, and the **emissions + rate-cap scenario** where a data-derived cap (\(0.8\times P95\)) illustrates trade-offs between peak constraints, cumulative production, and operational CO₂ proxy.

## Reports

- **Markdown report**: `reports/TECHNICAL_REPORT.md`
- **Overleaf report**: `reports/TECHNICAL_REPORT.tex` (upload with `reports/figures/`)

## Important note on emissions
This repo uses an **intensity proxy** (not metered facility emissions). Assumptions and limitations are explicitly documented.

