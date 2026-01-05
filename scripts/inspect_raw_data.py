#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _safe_read_csv(path: Path) -> pd.DataFrame:
    # Try common separators without being too clever.
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.read_csv(path, sep=";")


def _inspect_xlsx(path: Path, max_rows: int) -> dict[str, Any]:
    xl = pd.ExcelFile(path)
    sheets: dict[str, Any] = {}
    for sheet in xl.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except Exception as e:
            sheets[sheet] = {"error": str(e)}
            continue
        sheets[sheet] = {
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "columns": [str(c) for c in df.columns],
            "head": df.head(max_rows).to_dict(orient="records"),
        }
    return {"type": "xlsx", "sheets": sheets}


def _inspect_csv(path: Path, max_rows: int) -> dict[str, Any]:
    df = _safe_read_csv(path)
    return {
        "type": "csv",
        "shape": [int(df.shape[0]), int(df.shape[1])],
        "columns": [str(c) for c in df.columns],
        "head": df.head(max_rows).to_dict(orient="records"),
    }


def _inspect_parquet(path: Path, max_rows: int) -> dict[str, Any]:
    df = pd.read_parquet(path)
    return {
        "type": "parquet",
        "shape": [int(df.shape[0]), int(df.shape[1])],
        "columns": [str(c) for c in df.columns],
        "head": df.head(max_rows).to_dict(orient="records"),
    }


def inspect_path(raw_dir: Path, max_rows: int) -> dict[str, Any]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")

    exts = {".xlsx", ".xls", ".csv", ".parquet"}
    files = [p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    files = sorted(files)

    report: dict[str, Any] = {"raw_dir": str(raw_dir), "files": {}}
    for f in files:
        rel = str(f.relative_to(raw_dir))
        try:
            if f.suffix.lower() in (".xlsx", ".xls"):
                report["files"][rel] = _inspect_xlsx(f, max_rows=max_rows)
            elif f.suffix.lower() == ".csv":
                report["files"][rel] = _inspect_csv(f, max_rows=max_rows)
            elif f.suffix.lower() == ".parquet":
                report["files"][rel] = _inspect_parquet(f, max_rows=max_rows)
        except Exception as e:
            report["files"][rel] = {"error": str(e)}

    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect raw Volve (or any) data files: sheet names + columns + sample rows.")
    ap.add_argument("--raw", type=str, default="data/raw", help="Path to raw data directory (default: data/raw)")
    ap.add_argument("--max-rows", type=int, default=5, help="How many head rows to capture per table (default: 5)")
    ap.add_argument("--out", type=str, default="reports/schema_report.json", help="Output JSON path (default: reports/schema_report.json)")
    args = ap.parse_args()

    raw_dir = Path(args.raw)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = inspect_path(raw_dir=raw_dir, max_rows=args.max_rows)
    # Some cells (e.g., datetimes) may be pandas Timestamps which aren't JSON-serializable.
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    print(f"Wrote schema report: {out_path}")
    print(f"Inspected files: {len(report.get('files', {}))}")
    if len(report.get("files", {})) == 0:
        print("No .csv/.xlsx/.parquet files found under the raw directory.")


if __name__ == "__main__":
    main()


