from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .constants import DEFAULT_GUESS, ColumnGuess
from .io import normalize_columns, pick_first_existing


@dataclass(frozen=True)
class PreprocessConfig:
    date_col: str | None = None
    well_col: str | None = None
    oil_rate_col: str | None = None
    gas_rate_col: str | None = None
    water_rate_col: str | None = None
    on_stream_hrs_col: str | None = None
    # Optional operational/context signals (Volve Daily Production Data has these)
    avg_downhole_pressure_col: str | None = None
    avg_whp_col: str | None = None
    avg_choke_size_p_col: str | None = None
    dp_choke_size_col: str | None = None
    bore_wi_vol_col: str | None = None
    flow_kind_col: str | None = None
    well_type_col: str | None = None
    drop_negative_rates: bool = True


def _coerce_datetime(s: pd.Series) -> pd.Series:
    # Best-effort: supports strings, Excel serials, pandas datetime.
    dt = pd.to_datetime(s, errors="coerce", utc=True)
    # If everything is NaT, try treating as numeric Excel serial days.
    if dt.isna().all():
        as_num = pd.to_numeric(s, errors="coerce")
        # Excel's day 0 is 1899-12-30 in pandas' origin='1899-12-30' convention.
        dt = pd.to_datetime(as_num, unit="D", origin="1899-12-30", errors="coerce", utc=True)
    return dt.dt.tz_convert(None)


def _pick_or_override(df: pd.DataFrame, override: str | None, candidates: Iterable[str]) -> str | None:
    if override is not None and override in df.columns:
        return override
    return pick_first_existing(df, candidates)


def extract_daily_table(df: pd.DataFrame, cfg: PreprocessConfig, guess: ColumnGuess = DEFAULT_GUESS) -> pd.DataFrame | None:
    df = normalize_columns(df)

    date_col = _pick_or_override(df, cfg.date_col, guess.date)
    well_col = _pick_or_override(df, cfg.well_col, guess.well)
    oil_col = _pick_or_override(df, cfg.oil_rate_col, guess.oil_rate)
    gas_col = _pick_or_override(df, cfg.gas_rate_col, guess.gas_rate)
    wat_col = _pick_or_override(df, cfg.water_rate_col, guess.water_rate)
    on_stream_col = _pick_or_override(df, cfg.on_stream_hrs_col, guess.on_stream_hrs)

    # Optional operational signals (only kept if present)
    avg_downhole_pressure_col = _pick_or_override(
        df, cfg.avg_downhole_pressure_col, ("AVG_DOWNHOLE_PRESSURE", "Avg downhole pressure")
    )
    avg_whp_col = _pick_or_override(df, cfg.avg_whp_col, ("AVG_WHP_P", "Avg WHP"))
    avg_choke_size_p_col = _pick_or_override(df, cfg.avg_choke_size_p_col, ("AVG_CHOKE_SIZE_P", "Avg choke size %"))
    dp_choke_size_col = _pick_or_override(df, cfg.dp_choke_size_col, ("DP_CHOKE_SIZE", "DP choke size"))
    bore_wi_vol_col = _pick_or_override(df, cfg.bore_wi_vol_col, ("BORE_WI_VOL", "WI", "WATER_INJ_VOL"))
    flow_kind_col = _pick_or_override(df, cfg.flow_kind_col, ("FLOW_KIND",))
    well_type_col = _pick_or_override(df, cfg.well_type_col, ("WELL_TYPE",))

    # Require at least date + well + one of the rates.
    if date_col is None or well_col is None:
        return None
    if oil_col is None and gas_col is None and wat_col is None:
        return None

    out = pd.DataFrame()
    out["date"] = _coerce_datetime(df[date_col])
    out["well"] = df[well_col].astype(str).str.strip()

    def _rate(col: str | None) -> pd.Series:
        if col is None:
            return pd.Series([np.nan] * len(df))
        return pd.to_numeric(df[col], errors="coerce")

    out["q_oil"] = _rate(oil_col)
    out["q_gas"] = _rate(gas_col)
    out["q_water"] = _rate(wat_col)
    on_stream = pd.to_numeric(df[on_stream_col], errors="coerce") if on_stream_col else np.nan
    # Clean physically impossible values; clamp to [0, 24].
    if isinstance(on_stream, pd.Series):
        on_stream = on_stream.where(on_stream >= 0)
        on_stream = on_stream.clip(upper=24)
    out["on_stream_hrs"] = on_stream

    # Optional operational/context columns
    def _num_optional(col: str | None) -> pd.Series:
        if col is None:
            return pd.Series([np.nan] * len(df))
        return pd.to_numeric(df[col], errors="coerce")

    out["avg_downhole_pressure"] = _num_optional(avg_downhole_pressure_col)
    out["avg_whp"] = _num_optional(avg_whp_col)
    out["avg_choke_size_p"] = _num_optional(avg_choke_size_p_col)
    out["dp_choke_size"] = _num_optional(dp_choke_size_col)
    out["bore_wi_vol"] = _num_optional(bore_wi_vol_col)

    out["flow_kind"] = df[flow_kind_col].astype(str).str.strip() if flow_kind_col else pd.Series([pd.NA] * len(df))
    out["well_type"] = df[well_type_col].astype(str).str.strip() if well_type_col else pd.Series([pd.NA] * len(df))

    # Effective flowing rates (volumes scaled by uptime fraction).
    # If the reported volumes are daily totals and the well only flowed part of the day,
    # the effective flowing rate is higher than the daily-average rate.
    # We keep both; modeling can choose either.
    uptime_frac = out["on_stream_hrs"] / 24.0
    with np.errstate(divide="ignore", invalid="ignore"):
        out["q_oil_eff"] = out["q_oil"] / uptime_frac
        out["q_gas_eff"] = out["q_gas"] / uptime_frac
        out["q_water_eff"] = out["q_water"] / uptime_frac
    for c in ("q_oil_eff", "q_gas_eff", "q_water_eff"):
        out.loc[~np.isfinite(out[c]), c] = np.nan
        # Guard against negative effective rates (can occur due to data corrections).
        out.loc[out[c] < 0, c] = np.nan
        out.loc[out["on_stream_hrs"].isna() | (out["on_stream_hrs"] <= 0), c] = 0.0

    out = out.dropna(subset=["date", "well"], how="any")
    out = out.sort_values(["well", "date"]).reset_index(drop=True)

    if cfg.drop_negative_rates:
        for c in ("q_oil", "q_gas", "q_water"):
            out.loc[out[c] < 0, c] = np.nan

    return out


def merge_tables(tables: list[pd.DataFrame]) -> pd.DataFrame:
    if not tables:
        raise ValueError("No usable production-like tables found in provided inputs.")
    df = pd.concat(tables, ignore_index=True)
    # Aggregate in case multiple sources overlap:
    # For rates, we take sum (if they are components) OR max (if duplicates) is ambiguous.
    # We'll use sum but only where values exist; this is documented and can be changed later.
    df = (
        df.groupby(["well", "date"], as_index=False)
        .agg(
            q_oil=("q_oil", "sum"),
            q_gas=("q_gas", "sum"),
            q_water=("q_water", "sum"),
            # on_stream_hrs should never exceed 24; if duplicates exist, prefer max to avoid double-counting.
            on_stream_hrs=("on_stream_hrs", "max"),
            q_oil_eff=("q_oil_eff", "sum"),
            q_gas_eff=("q_gas_eff", "sum"),
            q_water_eff=("q_water_eff", "sum"),
            # Operational signals
            avg_downhole_pressure=("avg_downhole_pressure", "mean"),
            avg_whp=("avg_whp", "mean"),
            avg_choke_size_p=("avg_choke_size_p", "mean"),
            dp_choke_size=("dp_choke_size", "mean"),
            bore_wi_vol=("bore_wi_vol", "sum"),
            # Context labels (stable; pick first non-null)
            flow_kind=("flow_kind", lambda s: s.dropna().iloc[0] if len(s.dropna()) else pd.NA),
            well_type=("well_type", lambda s: s.dropna().iloc[0] if len(s.dropna()) else pd.NA),
        )
        .sort_values(["well", "date"])
        .reset_index(drop=True)
    )
    return df


