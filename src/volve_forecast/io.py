from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class ReadResult:
    path: Path
    df: pd.DataFrame
    sheet: str | None = None


def iter_data_files(input_path: str | Path) -> list[Path]:
    p = Path(input_path)
    if p.is_file():
        return [p]
    if not p.exists():
        raise FileNotFoundError(f"Input path does not exist: {p}")

    exts = (".csv", ".xlsx", ".xls", ".parquet")
    files: list[Path] = []
    for ext in exts:
        files.extend(sorted(p.rglob(f"*{ext}")))
    return files


def read_any(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        # Prefer reading all sheets so schema discovery + extraction can be systematic.
        # For large Excel files this can be heavy; Volve production Excel is small (~2–3MB).
        return pd.read_excel(path, sheet_name=None)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path}")


def read_all(input_path: str | Path) -> list[ReadResult]:
    results: list[ReadResult] = []
    for f in iter_data_files(input_path):
        try:
            df = read_any(f)
        except Exception:
            # Skip unreadable files; preprocessing will report if nothing usable is found.
            continue
        if isinstance(df, dict):
            # Excel: multiple sheets
            for sheet, sheet_df in df.items():
                if len(sheet_df.columns) == 0 or sheet_df.shape[0] == 0:
                    continue
                results.append(ReadResult(path=f, df=sheet_df, sheet=str(sheet)))
        else:
            if len(df.columns) == 0 or df.shape[0] == 0:
                continue
            results.append(ReadResult(path=f, df=df))
    return results


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def pick_first_existing(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    cols = set(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return None


