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

### 0) One-sentence intro (say this)
I used Equinor’s public Volve daily wellbore data to build a transparent QC→forecast→validation workflow, and extended it with operational signals (pressure/choke/injection), an operational CO₂ proxy, and a data-derived rate-cap scenario.

### 1) Pick the showcase well
Select **NO 15/9-F-14 H** (default).

### 2) Explain downtime
Open the **downtime** chart:
- These spikes are shut-ins/operational stops. Zeros during downtime are not reservoir decline.

### 3) Explain effective vs daily-average
Use **Effective (uptime-corrected)**:
- Daily totals mix in downtime. I compute \(q_{oil,eff} = q_{oil} / (on\_stream\_hrs/24)\) to approximate the flowing rate.

### 4) Show the forecasting baseline
Show **DCA fit** and **DCA backtest**:
- I fit exponential vs hyperbolic and select by AIC, then backtest with a time split (train on history, test on last 90 flowing days).

### 5) Show metrics (how to interpret)
- RMSE/MAE are in Sm³/day. I interpret them together with the backtest overlay and the operational-signal plots.

### 6) Operational signals (why DCA misses happen)
Open **Operational signals (pressure, choke, injection)**:
- Choke/pressure changes can create step changes and regime shifts that a smooth decline curve won’t predict.
- Injection activity and well role (producer vs injector) help explain stabilization or changes in decline behavior.

### 7) Emissions + scenario (job alignment)
Show emissions + scenario plot:
- Operational CO₂ is estimated using an intensity proxy (Scope 1+2). Assumptions/limitations are documented.
- I cap daily rate at \(0.8 \times P95\) (data-derived) to show a trade-off between peak constraints, cumulative production, and emissions.

## Reports

- **Markdown report**: `reports/TECHNICAL_REPORT.md`
- **Overleaf report**: `reports/TECHNICAL_REPORT.tex` (upload with `reports/figures/`)

## Important note on emissions
This repo uses an **intensity proxy** (not metered facility emissions). Assumptions and limitations are explicitly documented.

