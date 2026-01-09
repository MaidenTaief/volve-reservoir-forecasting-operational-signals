from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


def find_project_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    markers = {"requirements.txt", "src", "app", "reports"}
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


# ============================================================================
# WELL NOTES - Stats and context for each well
# ============================================================================

WELL_NOTES = {
    "NO 15/9-F-14 H": {
        "overview": "**Showcase well** — Longest history with **2,723 flowing days** (2008–2016). Horizontal producer with excellent data coverage.",
        "downtime": "Downtime spikes = shut-ins/maintenance. Zeros here are **operational**, not reservoir decline → filtered out for DCA.",
        "production": "**Effective rate** = rate while flowing, corrects for uptime. Example: 240 Sm³ in 6 hours → 960 Sm³/d effective.",
        "signals": "Operational signals explain DCA misses. **Choke changes** → step-changes in rate (operational). **Pressure trends** → depletion.",
        "dca": "**Exponential model** selected (lower AIC). Backtest **RMSE = 208.8 Sm³/d**. Higher error due to operational variability.",
        "metrics_detail": "• RMSE = 208.8 Sm³/d (penalizes large errors)\n• MAE = 208.6 Sm³/d (average miss)\n• Model = Exponential (simpler fit)",
        "emissions": "**Cumulative oil: 4.1 million Sm³**\n**CO₂ proxy: 287,665 tonnes** (70 kg/Sm³)\n*Proxy for scenario comparison, not reporting-grade.*",
        "scenario": "**Rate cap: 0.8×P95 = 3,380 Sm³/d**\nReduces production by **6%** (~246,000 Sm³)\nProportional emissions reduction.",
    },
    "NO 15/9-F-15 D": {
        "overview": "**Best DCA performer** — Clean decline profile with **683 training days**. Minimal operational effects.",
        "downtime": "Relatively consistent uptime. Cleaner operational pattern → DCA performs well here.",
        "production": "Smooth decline pattern — textbook behavior. Compare to F-14 H which has more variability.",
        "signals": "More stable signals than F-14 H. Less choke manipulation → reservoir decline dominates.",
        "dca": "**Hyperbolic model** selected. **RMSE = 34.8 Sm³/d** — lowest error. b ≈ 2 means fast early decline, then flattens.",
        "metrics_detail": "• RMSE = 34.8 Sm³/d (excellent)\n• MAE = 28.7 Sm³/d\n• Model = Hyperbolic\n• AIC = 5524",
        "emissions": "Lower cumulative production than F-14 H → proportionally lower emissions proxy.",
        "scenario": "Rate cap has less impact here — peak rates already lower and more consistent.",
    },
}

DEFAULT_NOTES = {
    "overview": "General workflow applies: filter to flowing days → fit decline curves → validate with time-based backtesting.",
    "downtime": "Check for shut-in periods. Zeros during downtime are operational → exclude from DCA fitting.",
    "production": "**Effective rate** = q_oil / (on_stream_hrs/24). Removes downtime dilution for cleaner decline signal.",
    "signals": "Pressure, choke, injection signals explain rate changes DCA can't predict (operational decisions).",
    "dca": "Exponential vs Hyperbolic selected via AIC. Backtest uses time-split (train early → test late).",
    "metrics_detail": "• RMSE: penalizes large errors (Sm³/d)\n• MAE: average absolute miss (Sm³/d)\n• AIC: model selection (lower = better)",
    "emissions": "CO₂ proxy: 70 kg/Sm³ oil intensity.\n*For scenario comparison, not reporting-grade.*",
    "scenario": "Rate cap = 0.8×P95 (data-derived). Shows trade-off between peak-rate limits and cumulative recovery.",
}


def get_note(well: str, note_type: str) -> str:
    if well in WELL_NOTES:
        return WELL_NOTES[well].get(note_type, DEFAULT_NOTES.get(note_type, ""))
    return DEFAULT_NOTES.get(note_type, "")


# ============================================================================
# STREAMLIT APP
# ============================================================================

st.set_page_config(page_title="Volve (Forecasting + Emissions)", layout="wide")

st.title("Volve: production forecasting + operational emissions (proxy)")
st.caption(
    "Real Equinor Volve daily wellbore data → QC → DCA baseline → backtest → operational CO₂ proxy → rate-cap scenario."
)

# Sidebar with key terms
st.sidebar.markdown("### Quick Reference")
st.sidebar.markdown("""
- **DCA** = Decline Curve Analysis
- **AIC** = Akaike Information Criterion (lower = better)
- **RMSE** = Root Mean Square Error (Sm³/d)
- **MAE** = Mean Absolute Error (Sm³/d)
- **Effective rate** = q_oil / (on_stream_hrs/24)
- **P95** = 95th percentile of rates
""")

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
    
    # Well overview note
    st.info(get_note(well, "overview"))
    
    st.markdown("**Chart options**")
    prod_layout = st.radio(
        "Production chart layout",
        ["Separate panels (recommended)", "Overlay (single axis)"],
        index=0,
        help="Gas volumes are often much larger than liquids, so separate panels are easier to read.",
    )
    y_scale = st.radio(
        "Y scale",
        ["Linear", "Log"],
        index=0,
        help="Log scale can help when gas is much larger than oil/water. Log requires positive values.",
    )

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
    st.caption(get_note(well, "production"))
    
    ts = d[["date", target_oil, target_gas, target_wat, "on_stream_hrs"]].copy()
    ts = ts.rename(columns={target_oil: "oil", target_gas: "gas", target_wat: "water"})

    selected_series = [c for c, enabled in [("oil", show_oil), ("gas", show_gas), ("water", show_water)] if enabled]
    if not selected_series:
        selected_series = ["oil"]

    # Small helper metrics: gas/oil ratio (GOR proxy) on flowing days
    flow = ts.copy()
    flow = flow[(flow["on_stream_hrs"].fillna(0) > 0)]
    # Avoid division by zero and ignore non-positive oil
    flow = flow[(flow["oil"].fillna(0) > 0) & (flow["gas"].fillna(0) >= 0)]
    if len(flow) >= 30 and "oil" in flow.columns and "gas" in flow.columns:
        gor = (flow["gas"] / flow["oil"]).replace([pd.NA, pd.NaT], pd.NA)
        gor = gor.replace([float("inf"), float("-inf")], pd.NA).dropna()
        if len(gor):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Median GOR (Sm³ gas / Sm³ oil)", f"{gor.median():.0f}")
            with c2:
                st.metric("P90 GOR", f"{gor.quantile(0.90):.0f}")
            with c3:
                st.metric("Flowing days used", f"{len(gor):,}")

    title = f"{well} — production ({'effective' if use_eff else 'daily-average'})"
    log_y = y_scale == "Log"

    if prod_layout.startswith("Separate"):
        long = ts.melt(id_vars=["date"], value_vars=selected_series, var_name="phase", value_name="value")
        long = long.dropna(subset=["value"])
        # For log scale: keep positive values only; otherwise plotly will error
        if log_y:
            long = long[long["value"] > 0]
            if long.empty:
                st.warning("Log scale requires positive values. Switch to Linear or select a different series/well.")
        phase_order = [p for p in ["oil", "gas", "water"] if p in selected_series]
        fig = px.line(
            long,
            x="date",
            y="value",
            facet_row="phase",
            category_orders={"phase": phase_order},
            title=title,
        )
        # Independent y-axes per panel; clean facet labels
        fig.update_yaxes(matches=None)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1].upper()))
        fig.update_layout(height=240 * len(phase_order) + 140, showlegend=False)
        if log_y:
            fig.update_yaxes(type="log")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Tip: separate panels use independent y-axes, so gas doesn’t hide oil/water trends.")
    else:
        # Overlay (single axis) — keep original behavior but allow log scale
        plot_ts = ts[["date"] + selected_series].copy()
        if log_y:
            # Drop non-positive values for each series to avoid log errors
            for s in selected_series:
                plot_ts.loc[plot_ts[s] <= 0, s] = pd.NA
            if plot_ts[selected_series].dropna(how="all").empty:
                st.warning("Log scale requires positive values. Switch to Linear or select a different series/well.")
        fig = px.line(plot_ts, x="date", y=selected_series, title=title)
        fig.update_layout(height=400, legend_title_text="Series")
        if log_y:
            fig.update_yaxes(type="log")
        st.plotly_chart(fig, use_container_width=True)
        if "gas" in selected_series:
            st.caption("Note: gas is often much larger than liquids (GOR). Use 'Separate panels' for easier reading.")

    # Downtime section
    st.subheader("Downtime / Uptime")
    st.caption(get_note(well, "downtime"))
    
    if uptime_view.startswith("Downtime"):
        ts2 = ts[["date", "on_stream_hrs"]].copy()
        ts2["downtime_hrs"] = (24.0 - ts2["on_stream_hrs"].fillna(0)).clip(lower=0, upper=24)
        fig2 = px.line(ts2, x="date", y="downtime_hrs", title=f"{well} — downtime hours")
        fig2.update_yaxes(range=[0, 24])
    else:
        fig2 = px.line(ts, x="date", y="on_stream_hrs", title=f"{well} — on-stream hours")
        fig2.update_yaxes(range=[0, 24])

    fig2.update_layout(height=250)
    st.plotly_chart(fig2, use_container_width=True)

# Operational signals section
st.divider()
st.subheader("Operational signals (pressure, choke, injection)")
st.caption(get_note(well, "signals"))

# Context labels
ctx_cols = [c for c in ["flow_kind", "well_type"] if c in d.columns]
if ctx_cols:
    ctx = d[ctx_cols].dropna().tail(1)
    if len(ctx):
        parts = []
        if "flow_kind" in ctx.columns:
            parts.append(f"**flow_kind:** {ctx.iloc[0]['flow_kind']}")
        if "well_type" in ctx.columns:
            parts.append(f"**well_type:** {ctx.iloc[0]['well_type']}")
        st.markdown(" | ".join(parts))

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
    default_sel = [c for c in ["avg_whp", "avg_choke_size_p"] if c in signal_options] or signal_options[:2]
    selected = st.multiselect(
        "Select signals to display",
        options=signal_options,
        default=default_sel,
        format_func=lambda c: labels.get(c, c),
    )

    if selected:
        # Time series plot
        sig_df = d[["date"] + selected].copy()
        sig_long = sig_df.melt(id_vars=["date"], var_name="signal", value_name="value").dropna(subset=["value"])
        sig_long["signal"] = sig_long["signal"].map(lambda c: labels.get(c, c))
        fig_s = px.line(sig_long, x="date", y="value", color="signal", title="Operational signals over time")
        fig_s.update_layout(height=300, legend_title_text="Signal")
        st.plotly_chart(fig_s, use_container_width=True)

        # Scatter plots with stats on left
        st.markdown("**Scatter vs oil rate** — helps identify regime changes / correlations")
        
        for c in selected:
            s = d[[c, target_oil, "on_stream_hrs"]].copy()
            s = s.dropna(subset=[c, target_oil])
            
            if len(s) >= 20:
                # Calculate stats for this signal
                corr = s[c].corr(s[target_oil])
                mean_val = s[c].mean()
                std_val = s[c].std()
                min_val = s[c].min()
                max_val = s[c].max()
                
                col_stats, col_chart = st.columns([1, 3])
                
                with col_stats:
                    st.markdown(f"**{labels.get(c, c)}**")
                    st.markdown(f"""
**Stats:**
- Mean: {mean_val:.1f}
- Std: {std_val:.1f}
- Range: {min_val:.1f} – {max_val:.1f}
- Corr with oil: {corr:.2f}
- Points: {len(s):,}
""")
                    if abs(corr) > 0.5:
                        st.success(f"Strong correlation ({corr:.2f})")
                    elif abs(corr) > 0.3:
                        st.warning(f"Moderate correlation ({corr:.2f})")
                    else:
                        st.info(f"Weak correlation ({corr:.2f})")
                
                with col_chart:
                    fig_sc = px.scatter(
                        s,
                        x=c,
                        y=target_oil,
                        color="on_stream_hrs",
                        labels={c: labels.get(c, c), target_oil: "Oil rate (Sm³/d)"},
                        color_continuous_scale="Viridis",
                        title=f"{labels.get(c, c)} vs Oil Rate",
                    )
                    fig_sc.update_layout(height=280)
                    st.plotly_chart(fig_sc, use_container_width=True)
else:
    st.info("Operational-signal columns not found. Re-run preprocessing to include pressure/choke/injection fields.")

st.divider()

# Forecasting section
colA, colB = st.columns(2)

with colA:
    st.subheader("Forecasting (DCA baseline)")
    st.markdown(get_note(well, "dca"))
    
    qc_oil = FIG_DIR / f"{safe_filename(well)}_{'q_oil_eff' if use_eff else 'q_oil'}.png"
    if qc_oil.exists():
        st.image(str(qc_oil), caption=f"QC plot: {qc_oil.name}", use_container_width=True)

    dca_fit = FIG_DIR / f"dca_fit_{safe_filename(well)}_q_oil_eff.png"
    dca_bt = FIG_DIR / f"dca_backtest_{safe_filename(well)}_q_oil_eff.png"

    if dca_fit.exists():
        st.image(str(dca_fit), caption="DCA fit (flowing days only)", use_container_width=True)
    if dca_bt.exists():
        st.image(str(dca_bt), caption="DCA backtest (train/test split)", use_container_width=True)

    if not qc_oil.exists() and not dca_fit.exists() and not dca_bt.exists():
        st.info("No precomputed DCA/QC figures found for this well.")

with colB:
    st.subheader("Emissions proxy + scenario")
    st.markdown(get_note(well, "emissions"))

    emissions_fig = FIG_DIR / f"emissions_{safe_filename(well)}_q_oil_eff.png"
    scenario_fig = FIG_DIR / f"scenario_rate_cap_p95_{safe_filename(well)}_q_oil_eff.png"

    if emissions_fig.exists():
        st.image(str(emissions_fig), caption="Cumulative oil + operational CO₂ proxy", use_container_width=True)
    else:
        st.info("Emissions plot not available for this well.")

    if scenario_fig.exists():
        st.markdown("---")
        st.markdown(get_note(well, "scenario"))
        st.image(str(scenario_fig), caption="Rate-cap scenario (0.8×P95)", use_container_width=True)
    else:
        st.info("Scenario plot not available for this well.")

st.divider()

# Metrics section
st.subheader("Backtest metrics")

if METRICS_PATH.exists():
    m = pd.read_csv(METRICS_PATH)
    if "dca_rmse" in m.columns and "rmse" not in m.columns:
        m = m.rename(columns={"dca_rmse": "rmse"})
    if "dca_mae" in m.columns and "mae" not in m.columns:
        m = m.rename(columns={"dca_mae": "mae"})
    if "dca_model" in m.columns and "model" not in m.columns:
        m = m.rename(columns={"dca_model": "model"})

    row = m[m["well"] == well]
    
    col_m1, col_m2 = st.columns([1, 2])
    
    with col_m1:
        st.markdown("**Metrics explained:**")
        st.markdown(get_note(well, "metrics_detail"))
    
    with col_m2:
        if len(row):
            cols = [c for c in ["well", "target", "horizon_days", "model", "rmse", "mae", "n_train", "n_test"] if c in row.columns]
            st.dataframe(row[cols] if cols else row, use_container_width=True, hide_index=True)
        else:
            st.info("No metrics row for this well (likely too short after flowing-day filtering).")

    with st.expander("All wells comparison"):
        if "rmse" in m.columns:
            show_cols = [c for c in ["well", "model", "rmse", "mae"] if c in m.columns]
            sorted_m = m.sort_values("rmse")
            st.dataframe(sorted_m[show_cols] if show_cols else sorted_m, use_container_width=True, hide_index=True)
            
            # Summary stats
            st.markdown(f"""
**Summary across all wells:**
- Best RMSE: **{sorted_m['rmse'].min():.1f} Sm³/d** ({sorted_m.iloc[0]['well']})
- Worst RMSE: **{sorted_m['rmse'].max():.1f} Sm³/d** ({sorted_m.iloc[-1]['well']})
- DCA works best when operations are stable; high variability → higher error.
""")
        else:
            st.dataframe(m, use_container_width=True, hide_index=True)
else:
    st.info(f"Metrics file not found: `{METRICS_PATH}`. Run the DCA notebook to generate it.")

st.divider()

# Report section
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
