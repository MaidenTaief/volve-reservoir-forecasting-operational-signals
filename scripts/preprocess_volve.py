#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from volve_forecast.io import read_all  # noqa: E402
from volve_forecast.preprocess import (  # noqa: E402
    PreprocessConfig,
    extract_daily_table,
    merge_tables,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Preprocess Volve production Excel/CSV into a clean per-well daily table.")
    ap.add_argument("--input", type=str, default="data/raw", help="Input path (file or directory). Default: data/raw")
    ap.add_argument(
        "--output",
        type=str,
        default="data/processed/volve_daily.parquet",
        help="Output path. Use .parquet if pyarrow/fastparquet is installed; otherwise .csv is safest.",
    )
    ap.add_argument("--prefer-sheet", type=str, default="Daily Production Data", help="Excel sheet name to prefer.")
    ap.add_argument("--date-col", type=str, default=None, help="Override date column name.")
    ap.add_argument("--well-col", type=str, default=None, help="Override well column name.")
    ap.add_argument("--oil-col", type=str, default=None, help="Override oil volume/rate column name.")
    ap.add_argument("--gas-col", type=str, default=None, help="Override gas volume/rate column name.")
    ap.add_argument("--water-col", type=str, default=None, help="Override water volume/rate column name.")
    args = ap.parse_args()

    cfg = PreprocessConfig(
        date_col=args.date_col,
        well_col=args.well_col,
        oil_rate_col=args.oil_col,
        gas_rate_col=args.gas_col,
        water_rate_col=args.water_col,
        on_stream_hrs_col=None,
        drop_negative_rates=True,
    )

    reads = read_all(args.input)
    if len(reads) == 0:
        raise SystemExit(f"No readable .csv/.xlsx/.parquet found under: {args.input}")

    # Prefer the daily production sheet if present.
    preferred = [r for r in reads if (r.sheet or "").strip() == args.prefer_sheet]
    candidates = preferred if preferred else reads

    tables: list[pd.DataFrame] = []
    for r in candidates:
        t = extract_daily_table(r.df, cfg)
        if t is None:
            continue
        tables.append(t)

    if not tables:
        # Provide a helpful error
        example = candidates[0]
        raise SystemExit(
            "Could not find a production-like table with date+well+rate columns.\n"
            f"First candidate: path={example.path} sheet={example.sheet}\n"
            f"Columns: {list(example.df.columns)[:50]}"
        )

    out = merge_tables(tables)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Write parquet when possible; otherwise fall back to CSV to avoid optional dependencies.
    wrote = False
    if out_path.suffix.lower() == ".parquet":
        try:
            out.to_parquet(out_path, index=False)
            wrote = True
        except Exception as e:
            csv_fallback = out_path.with_suffix(".csv")
            out.to_csv(csv_fallback, index=False)
            wrote = True
            print(
                "Parquet write failed (missing optional dependency is common). "
                f"Fell back to CSV: {csv_fallback}\nReason: {e}"
            )
            out_path = csv_fallback
    elif out_path.suffix.lower() == ".csv":
        out.to_csv(out_path, index=False)
        wrote = True
    else:
        # Default to CSV if extension is unknown
        csv_fallback = out_path.with_suffix(".csv")
        out.to_csv(csv_fallback, index=False)
        wrote = True
        out_path = csv_fallback

    if not wrote:
        raise SystemExit("Failed to write output dataset.")

    print(f"Wrote: {out_path}")
    print("Summary:")
    print(out.describe(include='all').transpose().head(20).to_string())
    print(f"wells={out['well'].nunique()} rows={len(out)} date_range={out['date'].min()}..{out['date'].max()}")


if __name__ == "__main__":
    main()


