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

## Demo script (2 minutes, interview-ready)

### 0) One sentence intro
“I used Equinor’s Volve daily wellbore production data to build a QC→forecast→validation workflow, and extended it with an operational CO₂ proxy and a data-derived rate-cap scenario to match the job’s forecasting + emissions + optimization themes.”

### 1) Pick the showcase well
Select **NO 15/9-F-14 H** (default).

### 2) Explain downtime
Open the **downtime** chart:
- “These spikes are shut-ins/operational stops. This is why zeros shouldn’t be interpreted as reservoir decline.”

### 3) Explain effective vs daily-average
Use **Effective (uptime-corrected)**:
- “Daily totals mix in downtime. I compute q_oil_eff = q_oil / (on_stream_hrs/24) to approximate the rate while flowing.”

### 4) Show the forecasting baseline
Show **DCA fit** and **DCA backtest**:
- “I fit exp vs hyperbolic and select by AIC. Then I backtest with a time split: train on early history, test on last 90 flowing days.”

### 5) Show metrics (how to interpret)
- “RMSE/MAE are in Sm³/day. I interpret them together with the plots (especially the backtest overlay and operational-signal section).”

### 6) Emissions and scenario (job alignment)
Show emissions + scenario plot:
- “Operational CO₂ is estimated using an intensity proxy (Scope 1+2). Assumptions are explicit in the report.
  Then I cap daily rate at 0.8×P95 (data-derived) to show a realistic trade-off between peak constraints, cumulative production, and emissions.”

## Reports

- **Markdown report**: `reports/TECHNICAL_REPORT.md`
- **Overleaf report**: `reports/TECHNICAL_REPORT.tex` (upload with `reports/figures/`)

## Important note on emissions
This repo uses an **intensity proxy** (not metered facility emissions). Assumptions and limitations are explicitly documented.

