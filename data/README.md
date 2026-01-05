# Data folder

Put downloaded Volve (raw) files under:

- `data/raw/`

Generated clean tables will be written to:

- `data/processed/`

## Data source (download yourself; not committed to git)

This project uses Equinor’s public Volve production dataset. In this repo, the Excel file is obtained via Kaggle:

- `https://www.kaggle.com/datasets/lamyalbert/volve-production-data`

Place the downloaded Excel here:

- `data/raw/Volve production data.xlsx`

Then run preprocessing (CSV output is the default used by the dashboard):

```bash
python scripts/preprocess_volve.py --input data/raw --output data/processed/volve_daily.csv
```

To **inspect schema** (sheet names + columns) without guessing, run:

```bash
python scripts/inspect_raw_data.py --raw data/raw --out reports/schema_report.json
```

Then share `reports/schema_report.json` (or paste the relevant parts) so we can lock the exact column mapping.


