from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


def find_project_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    markers = {"Equinor_Job.md", "requirements.txt", "src"}
    for cand in [p] + list(p.parents):
        hits = 0
        for m in markers:
            if (cand / m).exists():
                hits += 1
        if hits >= 2:
            return cand
    return p


def safe_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


PROJECT_ROOT = find_project_root()
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "volve_daily.csv"
METRICS_PATH_EXT = PROJECT_ROOT / "reports" / "dca_metrics_extended_q_oil_eff.csv"
METRICS_PATH_BASE = PROJECT_ROOT / "reports" / "dca_metrics_q_oil_eff.csv"
METRICS_PATH = METRICS_PATH_EXT if METRICS_PATH_EXT.exists() else METRICS_PATH_BASE
FIG_DIR = PROJECT_ROOT / "reports" / "figures"
REPORT_MD = PROJECT_ROOT / "reports" / "TECHNICAL_REPORT.md"
REPORT_TEX = PROJECT_ROOT / "reports" / "TECHNICAL_REPORT.tex"


st.set_page_config(page_title="Volve (Forecasting + Emissions)", layout="wide")

st.title("Volve: production forecasting + operational emissions (proxy)")
st.caption(
    "Real Equinor Volve daily wellbore data → QC → DCA baseline → backtest → operational CO₂ proxy → rate-cap scenario."
)

with st.expander("Glossary (plain English)", expanded=False):
    st.markdown(
        """
- **Wellbore**: the drilled hole/path (a well can have multiple wellbores over time).
- **On-stream hours**: how many hours the well flowed in that day (0–24).
- **Downtime**: 24 − on-stream hours (operational stop/shut-in).
- **q_oil (daily volume)**: total oil produced that day.
- **q_oil_eff (effective flowing rate)**: uptime-corrected rate while flowing: q_oil / (on_stream_hrs/24).
- **DCA (Decline Curve Analysis)**: classic reservoir-engineering baseline (exponential/hyperbolic decline).
- **AIC**: model selection score (balances fit quality vs complexity).
- **Backtest**: train on early time period, test on later time period.
- **RMSE/MAE**: error in the same units as the rate; RMSE penalizes large misses more.
"""
    )

with st.expander("How to interpret the charts (quick)", expanded=False):
    st.markdown(
        """
1) **Downtime chart**: spikes mean operational stops. Zeros in production during these periods should not be fitted as reservoir decline.
2) **Production chart**: compare daily-average vs effective (uptime-corrected) series.
3) **DCA fit/backtest**: fit is the baseline; backtest shows whether it predicts the last 90 days reasonably.
4) **Emissions proxy**: derived from cumulative oil using a documented intensity assumption (not metered emissions).
5) **Rate-cap scenario (0.8×P95)**: a data-derived cap that meaningfully constrains high-rate days and shows trade-offs.
"""
    )

if not DATA_PATH.exists():
    st.error(f"Missing dataset: `{DATA_PATH}`. Run preprocessing first.")
    st.stop()

# Load data

df = pd.read_csv(DATA_PATH)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date", "well"]).sort_values(["well", "date"]).reset_index(drop=True)

wells = sorted(df["well"].unique().tolist())

# Controls

left, right = st.columns([1, 2])
with left:
    st.subheader("Controls")
    well = st.selectbox("Wellbore", wells, index=wells.index("NO 15/9-F-14 H") if "NO 15/9-F-14 H" in wells else 0)
    series_mode = st.radio(
        "Production series",
        ["Effective (uptime-corrected)", "Daily-average"],
        index=0,
        help="Effective uses q_*_eff; daily-average uses q_* volumes as reported per day.",
    )
    uptime_view = st.radio(
        "Uptime view",
        ["Downtime hours (24 - on_stream_hrs)", "On-stream hours (0–24)"],
        index=0,
    )

    st.markdown("**Show series**")
    show_oil = st.checkbox("Oil", value=True)
    show_gas = st.checkbox("Gas", value=False)
    show_water = st.checkbox("Water", value=True)

use_eff = series_mode.startswith("Effective")

target_oil = "q_oil_eff" if use_eff else "q_oil"
target_gas = "q_gas_eff" if use_eff else "q_gas"
target_wat = "q_water_eff" if use_eff else "q_water"

# Slice well

d = df[df["well"] == well].copy()

with right:
    st.subheader("Production time series")
    ts = d[["date", target_oil, target_gas, target_wat, "on_stream_hrs"]].copy()
    ts = ts.rename(columns={target_oil: "oil", target_gas: "gas", target_wat: "water"})

    fig = px.line(
        ts,
        x="date",
        y=[c for c,enabled in [("oil",show_oil),("gas",show_gas),("water",show_water)] if enabled] or ["oil"],
        title=f"{well} — production ({'effective' if use_eff else 'daily-average'})",
    )
    fig.update_layout(height=420, legend_title_text="Series")
    st.plotly_chart(fig, width="stretch")

    st.caption(
        "Interpretation: effective series removes downtime dilution, making the decline behavior clearer for forecasting."
    )

    # Uptime/downtime
    if uptime_view.startswith("Downtime"):
        ts2 = ts[["date", "on_stream_hrs"]].copy()
        ts2["downtime_hrs"] = (24.0 - ts2["on_stream_hrs"].fillna(0)).clip(lower=0, upper=24)
        fig2 = px.line(ts2, x="date", y="downtime_hrs", title=f"{well} — downtime hours")
        fig2.update_yaxes(range=[0, 24])
    else:
        fig2 = px.line(ts, x="date", y="on_stream_hrs", title=f"{well} — on-stream hours")
        fig2.update_yaxes(range=[0, 24])

    fig2.update_layout(height=280)
    st.plotly_chart(fig2, width="stretch")
    st.caption("Downtime spikes indicate shut-ins/operational stops. We exclude these when fitting DCA.")

    st.subheader("Operational signals (pressure, choke, injection)")

    # Context (useful interview talking points)
    ctx_cols = [c for c in ["flow_kind", "well_type"] if c in d.columns]
    if ctx_cols:
        ctx = d[ctx_cols].dropna().tail(1)
        if len(ctx):
            parts = []
            if "flow_kind" in ctx.columns:
                parts.append(f"flow_kind: {ctx.iloc[0]['flow_kind']}")
            if "well_type" in ctx.columns:
                parts.append(f"well_type: {ctx.iloc[0]['well_type']}")
            st.caption(" | ".join(parts))

    signal_options: list[str] = []
    for c in ["avg_whp", "avg_downhole_pressure", "avg_choke_size_p", "dp_choke_size", "bore_wi_vol"]:
        if c in d.columns:
            signal_options.append(c)

    labels = {
        "avg_whp": "Avg WHP pressure",
        "avg_downhole_pressure": "Avg downhole pressure",
        "avg_choke_size_p": "Avg choke opening (%)",
        "dp_choke_size": "DP choke size",
        "bore_wi_vol": "Water injection volume",
    }

    if signal_options:
        default_sel = [c for c in ["avg_whp", "avg_choke_size_p", "bore_wi_vol"] if c in signal_options] or signal_options[:2]
        selected = st.multiselect(
            "Signals",
            options=signal_options,
            default=default_sel,
            format_func=lambda c: labels.get(c, c),
        )

        if selected:
            sig_df = d[["date"] + selected].copy()
            sig_long = sig_df.melt(id_vars=["date"], var_name="signal", value_name="value").dropna(subset=["value"])
            sig_long["signal"] = sig_long["signal"].map(lambda c: labels.get(c, c))
            fig_s = px.line(sig_long, x="date", y="value", color="signal")
            fig_s.update_layout(height=320, legend_title_text="Signal")
            st.plotly_chart(fig_s, width="stretch")

            st.caption("Scatter vs oil rate (helps explain regime changes / DCA misses)")
            for c in selected:
                s = d[[c, target_oil, "on_stream_hrs"]].copy()
                s = s.dropna(subset=[c, target_oil])
                if len(s) >= 20:
                    fig_sc = px.scatter(
                        s,
                        x=c,
                        y=target_oil,
                        color="on_stream_hrs",
                        labels={c: labels.get(c, c), target_oil: "Oil rate"},
                        color_continuous_scale="Viridis",
                    )
                    fig_sc.update_layout(height=300)
                    st.plotly_chart(fig_sc, width="stretch")
    else:
        st.info("Operational-signal columns not found. Re-run preprocessing to include pressure/choke/injection fields.")

st.divider()

# Precomputed figures

colA, colB = st.columns(2)
with colA:
    st.subheader("Forecasting (DCA baseline)")
    st.caption("DCA is a transparent reservoir-engineering baseline. The backtest uses a time split (last 90 days held out).")

    qc_oil = FIG_DIR / f"{safe_filename(well)}_{'q_oil_eff' if use_eff else 'q_oil'}.png"
    if qc_oil.exists():
        st.image(str(qc_oil), caption=f"QC plot: {qc_oil.name}", width="stretch")

    dca_fit = FIG_DIR / f"dca_fit_{safe_filename(well)}_q_oil_eff.png"
    dca_bt = FIG_DIR / f"dca_backtest_{safe_filename(well)}_q_oil_eff.png"

    if dca_fit.exists():
        st.image(str(dca_fit), caption="DCA fit (flowing days only)", width="stretch")
    if dca_bt.exists():
        st.image(str(dca_bt), caption="DCA backtest (train vs test split)", width="stretch")

    if not qc_oil.exists() and not dca_fit.exists() and not dca_bt.exists():
        st.info("No precomputed DCA/QC figures found for this well.")

with colB:
    st.subheader("Emissions proxy + scenario")
    st.caption(
        "Operational CO₂ is estimated with an intensity proxy (Scope 1+2). This is not metered emissions; assumptions are documented in the report."
    )

    emissions_fig = FIG_DIR / f"emissions_{safe_filename(well)}_q_oil_eff.png"
    scenario_fig = FIG_DIR / f"scenario_rate_cap_p95_{safe_filename(well)}_q_oil_eff.png"

    if emissions_fig.exists():
        st.image(str(emissions_fig), caption="Cumulative oil + operational CO₂ proxy", width="stretch")
    else:
        st.info("Emissions plot not available for this well (currently generated for showcase well).")

    if scenario_fig.exists():
        st.image(
            str(scenario_fig),
            caption="Scenario: cap daily rate at 0.8×P95 (data-derived) → cumulative oil + CO₂ trade-off",
            width="stretch",
        )
    else:
        st.info("Scenario plot not available for this well (currently generated for showcase well).")

st.divider()

st.subheader("Backtest metrics (simple)")
st.caption("We keep this simple for interview clarity: RMSE + MAE in engineering units (Sm³/d).")

if METRICS_PATH.exists():
    m = pd.read_csv(METRICS_PATH)
    # Normalize extended-vs-base metric column names so the UI stays stable.
    if "dca_rmse" in m.columns and "rmse" not in m.columns:
        m = m.rename(columns={"dca_rmse": "rmse"})
    if "dca_mae" in m.columns and "mae" not in m.columns:
        m = m.rename(columns={"dca_mae": "mae"})
    if "dca_model" in m.columns and "model" not in m.columns:
        m = m.rename(columns={"dca_model": "model"})

    row = m[m["well"] == well]
    if len(row):
        cols = [c for c in ["well", "target", "horizon_days", "model", "rmse", "mae", "n_train", "n_test", "train_end", "test_end"] if c in row.columns]
        st.dataframe(row[cols] if cols else row, width="stretch", hide_index=True)
    else:
        st.info("No metrics row for this well (likely too short after flowing-day filtering).")

    with st.expander("All wells"):
        if "rmse" in m.columns:
            show_cols = [c for c in ["well", "model", "rmse", "mae"] if c in m.columns]
            st.dataframe(m.sort_values("rmse")[show_cols] if show_cols else m.sort_values("rmse"), width="stretch", hide_index=True)
        else:
            st.dataframe(m, width="stretch", hide_index=True)
else:
    st.info(f"Metrics file not found: `{METRICS_PATH}`. Run the DCA notebook to generate it.")

st.divider()

st.subheader("Report")
cols = st.columns(2)
with cols[0]:
    if REPORT_MD.exists():
        st.download_button("Download report (Markdown)", REPORT_MD.read_text(), file_name="TECHNICAL_REPORT.md", mime="text/markdown")
with cols[1]:
    if REPORT_TEX.exists():
        st.download_button("Download report (LaTeX/Overleaf)", REPORT_TEX.read_text(), file_name="TECHNICAL_REPORT.tex", mime="text/plain")

if REPORT_MD.exists():
    with st.expander("Read report (markdown)", expanded=False):
        st.markdown(REPORT_MD.read_text())
