#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from volve_forecast.dca import fit_best  # noqa: E402


def make_flowing_series(df: pd.DataFrame, well: str, target: str) -> pd.DataFrame:
    d = df[df["well"] == well].copy().sort_values("date")
    d = d[(d["on_stream_hrs"].fillna(0) > 0) & (d[target].fillna(0) > 0)].copy()
    d = d.dropna(subset=["date", target])
    d = d.sort_values("date")
    d["t_days"] = (d["date"] - d["date"].min()).dt.days.astype(float)
    return d.reset_index(drop=True)


def smape(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.mean(2 * np.abs(y - yhat) / (np.abs(y) + np.abs(yhat) + 1e-9)))


def wape(y: np.ndarray, yhat: np.ndarray) -> float:
    denom = float(np.sum(np.abs(y))) + 1e-9
    return float(np.sum(np.abs(y - yhat)) / denom)


def mase(y: np.ndarray, yhat: np.ndarray, y_train: np.ndarray) -> float:
    # Non-seasonal MASE scaling: mean absolute one-step naive error on training
    scale = float(np.mean(np.abs(np.diff(y_train))))
    scale = max(scale, 1e-9)
    return float(np.mean(np.abs(y - yhat)) / scale)


def backtest_split(t: np.ndarray, horizon_days: int = 90, min_train_days: int = 120) -> float:
    t_end = float(t.max())
    return max(float(t.min()) + min_train_days, t_end - horizon_days)


def eval_one_well(d: pd.DataFrame, target: str, horizon_days: int = 90, min_train_days: int = 120) -> dict | None:
    if len(d) < (min_train_days + 30):
        return None

    t = d["t_days"].to_numpy(dtype=float)
    y = d[target].to_numpy(dtype=float)
    split = backtest_split(t, horizon_days=horizon_days, min_train_days=min_train_days)

    train_mask = t <= split
    test_mask = t > split
    if train_mask.sum() < 30 or test_mask.sum() < 10:
        return None

    t_train, y_train = t[train_mask], y[train_mask]
    t_test, y_test = t[test_mask], y[test_mask]

    # DCA
    fit = fit_best(t_train, y_train)
    yhat_dca = fit.predict(t_test)

    # Naive baseline: last observed train value
    yhat_naive = np.full_like(y_test, fill_value=y_train[-1], dtype=float)

    def metrics(y_true, yhat, y_train):
        rmse = float(np.sqrt(np.mean((y_true - yhat) ** 2)))
        mae = float(np.mean(np.abs(y_true - yhat)))
        return {
            "rmse": rmse,
            "mae": mae,
            "smape": smape(y_true, yhat),
            "wape": wape(y_true, yhat),
            "mase": mase(y_true, yhat, y_train),
        }

    m_dca = metrics(y_test, yhat_dca, y_train)
    m_nv = metrics(y_test, yhat_naive, y_train)

    # Relative improvement in MAE (positive = better than naive)
    rel_mae_impr = 1.0 - (m_dca["mae"] / (m_nv["mae"] + 1e-9))

    return {
        "well": d["well"].iloc[0],
        "target": target,
        "horizon_days": horizon_days,
        "n_train": int(train_mask.sum()),
        "n_test": int(test_mask.sum()),
        "train_start": str(d["date"].iloc[0].date()),
        "train_end": str((d["date"].min() + pd.to_timedelta(split, unit="D")).date()),
        "test_end": str(d["date"].iloc[-1].date()),
        "dca_model": fit.model,
        "dca_params": str(fit.params),
        "dca_aic": float(fit.aic),
        **{f"dca_{k}": v for k, v in m_dca.items()},
        **{f"naive_{k}": v for k, v in m_nv.items()},
        "dca_vs_naive_mae_improvement": float(rel_mae_impr),
    }


def main() -> None:
    data_path = PROJECT_ROOT / "data" / "processed" / "volve_daily.csv"
    if not data_path.exists():
        raise SystemExit(f"Missing dataset: {data_path}")

    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "well"]).sort_values(["well", "date"]).reset_index(drop=True)

    target = "q_oil_eff"
    rows = []
    for well in df["well"].unique():
        d = make_flowing_series(df, well, target)
        if len(d) == 0:
            continue
        r = eval_one_well(d, target)
        if r:
            rows.append(r)

    out = pd.DataFrame(rows)
    reports = PROJECT_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    out_path = reports / "dca_metrics_extended_q_oil_eff.csv"
    out.sort_values("dca_rmse").to_csv(out_path, index=False)

    print("Wrote:", out_path)
    if len(out):
        print(out[["well", "dca_rmse", "dca_wape", "dca_mase", "naive_rmse", "dca_vs_naive_mae_improvement"]])


if __name__ == "__main__":
    main()
