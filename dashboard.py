# dashboard.py
"""
Streamlit-powered DCF Valuation Dashboard.

Usage:
    streamlit run dashboard.py

Provides an interactive interface for running DCF valuations with
adjustable assumptions, scenario analysis, sensitivity heatmaps,
and downloadable PDF reports.
"""

from __future__ import annotations

import os
import sys
import tempfile

import streamlit as st
import plotly.graph_objects as go
import numpy as np

from utils.finance import fetch_ticker_data, TickerData
from models.wacc import WACCInputs
from models.forecasting import ForecastInputs
from models.dcf import DCFInputs, DCFResult, ManualDCFInputs, run_dcf
from models.valuation import run_scenario_analysis, run_sensitivity_analysis
from models.solver import solve_missing_variable
from utils.helpers import generate_pdf_report


# ──────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DCF Valuation Model",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #1E3A5F 0%, #0F1B2D 100%);
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        border: 1px solid rgba(59, 130, 246, 0.3);
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
    }
    .metric-card .value {
        font-size: 28px;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 4px;
    }
    .metric-card .label {
        font-size: 12px;
        font-weight: 500;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Verdict badges */
    .badge-under {
        background: linear-gradient(135deg, #22C55E, #16A34A);
        color: white; padding: 6px 16px; border-radius: 20px;
        font-weight: 600; font-size: 13px; display: inline-block;
    }
    .badge-fair {
        background: linear-gradient(135deg, #F59E0B, #D97706);
        color: white; padding: 6px 16px; border-radius: 20px;
        font-weight: 600; font-size: 13px; display: inline-block;
    }
    .badge-over {
        background: linear-gradient(135deg, #EF4444, #DC2626);
        color: white; padding: 6px 16px; border-radius: 20px;
        font-weight: 600; font-size: 13px; display: inline-block;
    }

    /* Section dividers */
    .section-divider {
        border: none;
        border-top: 2px solid #E2E8F0;
        margin: 24px 0;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# Manual DCF Session State Initialization
# ──────────────────────────────────────────────────────────────────────
# Initialize every manual-mode input key exactly once.  Using
# setdefault() ensures we never overwrite a value that the user or the
# solver callback has already written, which is the critical guard
# against Streamlit's re-render-on-state-change loop.

_MANUAL_DEFAULTS = {
    "manual_n":          5,
    "manual_m":          1,
    "manual_mid_year":   False,
    "manual_cf0":        -1_000_000.0,
    "manual_cfs":        [200_000.0, 250_000.0, 300_000.0, 350_000.0, 400_000.0],
    "manual_tv":         500_000.0,
    "manual_wacc":       0.10,
    "manual_g":          0.025,
    "manual_target_pv":  0.0,
    "manual_target_npv": 0.0,
    # Which variable the solver should solve for (the one set to None).
    # Must be one of: "manual_cf0", "manual_target_pv",
    #                 "manual_wacc", "manual_g".
    "manual_solve_for":  "manual_target_pv",
    # Last solver result metadata (read-only display).
    "manual_solver_result": None,
    "manual_solver_error":  None,
}

for _key, _default in _MANUAL_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _default


# ──────────────────────────────────────────────────────────────────────
# Industry-Standard Input Parsing Utilities
# ──────────────────────────────────────────────────────────────────────
# Users can type values like "14%", "$1,000,000", "2.5M", "500K",
# "-$15,000", or plain decimals.  These functions normalize the raw
# text into the float that the engine expects.

import re as _re


def _parse_rate(text: str) -> float:
    """Parse a rate string into a decimal float.

    Accepted formats:
        '14%'    → 0.14
        '14.5%'  → 0.145
        '0.14'   → 0.14
        '14'     → 0.14  (values > 1 are treated as percentages)
        '-5%'    → -0.05
    """
    s = text.strip().replace(",", "")
    if not s:
        return 0.0
    if s.endswith("%"):
        return float(s[:-1]) / 100.0
    val = float(s)
    # Heuristic: if abs > 1, user almost certainly typed a percentage
    if abs(val) > 1.0:
        return val / 100.0
    return val


def _parse_currency(text: str) -> float:
    """Parse a currency string into a raw float.

    Accepted formats:
        '$1,000,000'  → 1000000.0
        '1,000,000'   → 1000000.0
        '1M' / '1m'   → 1000000.0
        '2.5B' / '2.5b' → 2500000000.0
        '500K' / '500k' → 500000.0
        '-$15,000'    → -15000.0
        '15000'       → 15000.0
    """
    s = text.strip().replace(",", "").replace("$", "")
    if not s:
        return 0.0

    # Detect sign
    sign = 1.0
    if s.startswith("-"):
        sign = -1.0
        s = s[1:].strip()
    elif s.startswith("+"):
        s = s[1:].strip()

    # Detect suffix multipliers
    multiplier = 1.0
    if s and s[-1].upper() == "B":
        multiplier = 1e9
        s = s[:-1]
    elif s and s[-1].upper() == "M":
        multiplier = 1e6
        s = s[:-1]
    elif s and s[-1].upper() == "K":
        multiplier = 1e3
        s = s[:-1]

    return sign * float(s) * multiplier


def _fmt_rate(val: float) -> str:
    """Format a decimal rate for display in a text input.  e.g. 0.14 → '14.00%'"""
    return f"{val * 100:.2f}%"


def _fmt_currency(val: float) -> str:
    """Format a raw float for display in a text input.  e.g. 1000000 → '$1,000,000.00'"""
    if val < 0:
        return f"-${abs(val):,.2f}"
    return f"${val:,.2f}"


# ──────────────────────────────────────────────────────────────────────
# Manual DCF Solver Callback
# ──────────────────────────────────────────────────────────────────────
# This function is invoked via on_click / on_change BEFORE the next
# page render.  It reads widget values from session_state, constructs
# the ManualDCFInputs with the designated target set to None, runs the
# solver, and writes the answer back into session_state.  Because the
# write happens inside a callback (not inline), Streamlit will pick up
# the updated value in the same render cycle without triggering a
# secondary re-run — preventing the infinite-loop problem.

_SOLVE_TARGET_MAP = {
    "manual_cf0":       "initial_outlay_cf0",
    "manual_target_pv": "target_pv",
    "manual_wacc":      "wacc",
    "manual_g":         "perpetual_growth",
}


def run_valuation_solver() -> None:
    """Read session_state → build ManualDCFInputs → solve → write back."""
    solve_for = st.session_state["manual_solve_for"]
    st.session_state["manual_solver_error"] = None
    st.session_state["manual_solver_result"] = None

    try:
        # ── Read current state ───────────────────────────────────────
        n   = int(st.session_state["manual_n"])
        m   = int(st.session_state["manual_m"])
        mid = bool(st.session_state["manual_mid_year"])
        cf0 = float(st.session_state["manual_cf0"])
        cfs = [float(v) for v in st.session_state["manual_cfs"][:n]]
        tv  = float(st.session_state["manual_tv"])
        w   = float(st.session_state["manual_wacc"])
        g   = float(st.session_state["manual_g"])
        tpv = float(st.session_state["manual_target_pv"])
        npv = float(st.session_state["manual_target_npv"])
        nd  = 0.0   # net_debt — currently not surfaced as an input
        so  = 1.0   # shares_outstanding — currently not surfaced

        # ── Pad / trim cash_flows to match n ─────────────────────────
        if len(cfs) < n:
            cfs.extend([0.0] * (n - len(cfs)))
        elif len(cfs) > n:
            cfs = cfs[:n]

        # ── Build kwargs, setting the solve-target to None ───────────
        kwargs = dict(
            projection_period_n=n,
            compounding_m=m,
            mid_year_convention=mid,
            initial_outlay_cf0=cf0,
            cash_flows=cfs,
            terminal_value=tv,
            wacc=w,
            perpetual_growth=g,
            target_npv=npv,
            target_pv=tpv,
            net_debt=nd,
            shares_outstanding=so,
        )

        # Map the session-state key to the ManualDCFInputs field name
        dcf_field = _SOLVE_TARGET_MAP[solve_for]
        kwargs[dcf_field] = None

        inputs = ManualDCFInputs(**kwargs)

        # ── Solve ────────────────────────────────────────────────────
        result = solve_missing_variable(inputs)
        solved_value = result["value"]

        # ── Write the answer back into session_state ─────────────────
        st.session_state[solve_for] = solved_value
        st.session_state["manual_solver_result"] = result

    except Exception as exc:
        st.session_state["manual_solver_error"] = str(exc)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

DEFAULT_RISK_FREE_RATE = 0.043
DEFAULT_EQUITY_RISK_PREMIUM = 0.055
DEFAULT_COST_OF_DEBT_PRETAX = 0.055
DEFAULT_TAX_RATE = 0.21


def _metric_card(value: str, label: str) -> str:
    return f"""
    <div class="metric-card">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """


def _build_wacc_inputs(data: TickerData, wacc_override: float | None = None) -> WACCInputs:
    """Build WACC inputs, optionally overriding the effective WACC."""
    beta = max(data.beta, 0.5)

    equity_mv = data.market_cap if data.market_cap > 0 else data.current_price * data.shares_outstanding
    debt_mv = max(data.total_debt, 0.0)
    total_capital = equity_mv + debt_mv

    if total_capital > 0:
        equity_ratio = equity_mv / total_capital
        debt_ratio = debt_mv / total_capital
    else:
        equity_ratio = 1.0
        debt_ratio = 0.0

    equity_ratio = round(equity_ratio, 10)
    debt_ratio = round(1.0 - equity_ratio, 10)

    # If WACC override is set, reverse-solve for ERP
    if wacc_override is not None:
        kd_at = DEFAULT_COST_OF_DEBT_PRETAX * (1.0 - DEFAULT_TAX_RATE)
        if equity_ratio * beta > 0:
            erp = (wacc_override - debt_ratio * kd_at - equity_ratio * DEFAULT_RISK_FREE_RATE) / (equity_ratio * beta)
            erp = max(0.01, erp)
        else:
            erp = DEFAULT_EQUITY_RISK_PREMIUM
    else:
        erp = DEFAULT_EQUITY_RISK_PREMIUM

    return WACCInputs(
        risk_free_rate=DEFAULT_RISK_FREE_RATE,
        beta=beta,
        equity_risk_premium=erp,
        cost_of_debt_pretax=DEFAULT_COST_OF_DEBT_PRETAX,
        tax_rate=DEFAULT_TAX_RATE,
        debt_ratio=debt_ratio,
        equity_ratio=equity_ratio,
    )


def _build_forecast_inputs(
    data: TickerData,
    growth_override: float | None = None,
    n_years: int = 5,
) -> ForecastInputs:
    """Build forecast inputs with optional growth rate override."""
    if growth_override is not None:
        avg_growth = growth_override
    elif data.revenue_growth_rates:
        avg_growth = sum(data.revenue_growth_rates) / len(data.revenue_growth_rates)
    else:
        avg_growth = 0.08

    avg_growth = max(0.02, min(avg_growth, 0.40))
    growth_rates = []
    g = avg_growth
    for _ in range(n_years):
        growth_rates.append(round(max(0.02, g), 4))
        g *= 0.80

    current_margin = data.latest_ebit_margin if data.latest_ebit_margin > 0 else 0.15
    target_margin = 0.20
    ebit_margins = []
    for i in range(n_years):
        weight = (i + 1) / n_years
        margin = current_margin + (target_margin - current_margin) * weight * 0.5
        ebit_margins.append(round(max(0.05, margin), 4))

    return ForecastInputs(
        base_revenue=data.latest_revenue,
        revenue_growth_rates=growth_rates,
        ebit_margins=ebit_margins,
        tax_rates=[DEFAULT_TAX_RATE] * n_years,
        depreciation_pct_of_rev=[0.03] * n_years,
        capex_pct_of_rev=[0.05] * min(2, n_years) + [0.04] * max(0, n_years - 2),
        nwc_pct_of_rev_change=[0.08] * n_years,
        projection_years=n_years,
    )


# ──────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## DCF Valuation Model")
    st.markdown("---")

    ticker_input = st.text_input(
        "Ticker Symbol",
        value="AAPL",
        max_chars=10,
        help="Enter any valid Yahoo Finance ticker symbol.",
    )

    fetch_btn = st.button("Fetch Live Data", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### Model Assumptions")

    growth_rate = st.slider(
        "Revenue Growth Rate (Yr 1)",
        min_value=0.0, max_value=40.0, value=8.0,
        step=1.0, format="%.0f%%",
        help="Year-1 revenue growth rate. Decays ~20% per year.",
    )

    wacc_val = st.slider(
        "WACC (Discount Rate)",
        min_value=5.0, max_value=18.0, value=10.0,
        step=0.5, format="%.1f%%",
        help="Weighted average cost of capital used to discount FCFs.",
    )

    terminal_growth = st.slider(
        "Terminal Growth Rate",
        min_value=1.0, max_value=5.0, value=2.5,
        step=0.1, format="%.1f%%",
        help="Perpetuity growth rate for the Gordon Growth Model.",
    )

    forecast_years = st.slider(
        "Forecast Years",
        min_value=3, max_value=10, value=5,
        step=1,
        help="Number of explicit projection years.",
    )

    st.markdown("---")
    st.markdown(
        "<p style='font-size:11px; color:#94A3B8; text-align:center;'>"
        "Data sourced from Yahoo Finance via yfinance.<br>"
        "For informational purposes only.</p>",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
# Fetch data
# ──────────────────────────────────────────────────────────────────────

if fetch_btn or "ticker_data" not in st.session_state:
    if fetch_btn:
        symbol = ticker_input.upper().strip()
        if symbol:
            with st.spinner(f"Fetching live data for {symbol}..."):
                try:
                    st.session_state["ticker_data"] = fetch_ticker_data(symbol)
                    st.session_state["fetch_error"] = None
                except Exception as e:
                    st.session_state["fetch_error"] = str(e)

if "ticker_data" not in st.session_state:
    st.markdown("## Welcome to the DCF Valuation Dashboard")

# ──────────────────────────────────────────────────────────────────────
# Tabs Layout
# ──────────────────────────────────────────────────────────────────────
tab_live, tab_manual = st.tabs(["🏢 Live Ticker DCF", "🧮 Manual N-1 Solver"])

with tab_live:
    if "ticker_data" not in st.session_state:
        st.markdown("## Live Ticker DCF Valuation")
        st.markdown(
            "Enter a **ticker symbol** in the sidebar and click "
            "**Fetch Live Data** to begin."
        )
    elif st.session_state.get("fetch_error"):
        st.error(f"Failed to fetch data: {st.session_state['fetch_error']}")
    else:
        data: TickerData = st.session_state["ticker_data"]

        wacc_dec = wacc_val / 100.0
        growth_dec = growth_rate / 100.0
        tgr_dec = terminal_growth / 100.0

        wacc_inputs = _build_wacc_inputs(data, wacc_override=wacc_dec)
        forecast_inputs = _build_forecast_inputs(
            data, growth_override=growth_dec, n_years=forecast_years,
        )
        
        dcf_inputs = DCFInputs(
            wacc_inputs=wacc_inputs,
            forecast_inputs=forecast_inputs,
            terminal_growth_rate=tgr_dec,
            net_debt=data.net_debt,
            shares_outstanding=data.shares_outstanding,
        )
        
        try:
            result = run_dcf(dcf_inputs)
        except ValueError as e:
            st.error(f"Model Error: {e}")
            st.stop()
        
        
        # ──────────────────────────────────────────────────────────────────────
        # Header
        # ──────────────────────────────────────────────────────────────────────
        
        st.markdown(f"# {data.company_name} ({data.ticker})")
        
        intrinsic = result.implied_share_price
        current = data.current_price
        mos = (intrinsic - current) / intrinsic if intrinsic > 0 else -1.0
        
        if mos > 0.15:
            badge = '<span class="badge-under">UNDERVALUED</span>'
        elif mos > 0:
            badge = '<span class="badge-fair">FAIRLY VALUED</span>'
        else:
            badge = '<span class="badge-over">OVERVALUED</span>'
        
        # Key metrics row
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(_metric_card(f"${intrinsic:,.2f}", "Intrinsic Value"), unsafe_allow_html=True)
        with c2:
            st.markdown(_metric_card(f"${current:,.2f}", "Market Price"), unsafe_allow_html=True)
        with c3:
            st.markdown(_metric_card(f"{mos:.1%}", "Margin of Safety"), unsafe_allow_html=True)
        with c4:
            st.markdown(
                _metric_card(badge, "Recommendation"),
                unsafe_allow_html=True,
            )
        
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        
        
        # ──────────────────────────────────────────────────────────────────────
        # WACC & Assumptions
        # ──────────────────────────────────────────────────────────────────────
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("### WACC Breakdown")
            w = result.wacc_result
            wacc_data = {
                "Component": [
                    "Cost of Equity (CAPM)",
                    "Cost of Debt (after-tax)",
                    "Equity Weight",
                    "Debt Weight",
                    "**WACC**",
                ],
                "Value": [
                    f"{w.cost_of_equity:.2%}",
                    f"{w.cost_of_debt_aftertax:.2%}",
                    f"{w.equity_ratio:.1%}",
                    f"{w.debt_ratio:.1%}",
                    f"**{w.wacc:.2%}**",
                ],
            }
            st.table(wacc_data)
        
        with col_right:
            st.markdown("### Forecast Assumptions")
            fi = forecast_inputs
            import pandas as pd
            assumptions_df = pd.DataFrame({
                "Year": [f"Yr {i+1}" for i in range(forecast_years)],
                "Growth": [f"{g:.1%}" for g in fi.revenue_growth_rates],
                "Margin": [f"{m:.1%}" for m in fi.ebit_margins],
                "Tax": [f"{t:.1%}" for t in fi.tax_rates],
                "CapEx %": [f"{c:.1%}" for c in fi.capex_pct_of_rev],
            })
            st.dataframe(assumptions_df, use_container_width=True, hide_index=True)
        
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        
        
        # ──────────────────────────────────────────────────────────────────────
        # FCF Projections
        # ──────────────────────────────────────────────────────────────────────
        
        st.markdown("### Projected Free Cash Flows")
        
        fcf_rows = []
        for dy in result.discounted_years:
            proj = result.forecast_result.projections[dy.year - 1]
            fcf_rows.append({
                "Year": f"Year {dy.year}",
                "Revenue": f"${proj.revenue / 1e6:,.1f}M",
                "EBIT": f"${proj.ebit / 1e6:,.1f}M",
                "NOPAT": f"${proj.nopat / 1e6:,.1f}M",
                "FCF": f"${dy.fcf / 1e6:,.1f}M",
                "PV(FCF)": f"${dy.present_value_fcf / 1e6:,.1f}M",
            })
        fcf_df = pd.DataFrame(fcf_rows)
        st.dataframe(fcf_df, use_container_width=True, hide_index=True)
        
        # Valuation bridge
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            st.metric("Enterprise Value", f"${result.enterprise_value / 1e9:,.2f}B")
        with bc2:
            st.metric("Less: Net Debt", f"${result.net_debt / 1e9:,.2f}B")
        with bc3:
            st.metric("Equity Value", f"${result.equity_value / 1e9:,.2f}B")
        
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        
        
        # ──────────────────────────────────────────────────────────────────────
        # Scenario Analysis
        # ──────────────────────────────────────────────────────────────────────
        
        st.markdown("### Scenario Analysis")
        
        scenarios = run_scenario_analysis(dcf_inputs)
        
        sc_cols = st.columns(3)
        scenario_icons = {"Bull": ("arrow_upper_right", "#22C55E"), "Base": ("balance", "#3B82F6"), "Bear": ("arrow_lower_right", "#EF4444")}
        
        for i, s in enumerate(scenarios):
            with sc_cols[i]:
                r = s.dcf_result
                iv = r.implied_share_price
                sc_mos = (iv - current) / iv if iv > 0 else -1.0
                color = scenario_icons.get(s.name, ("", "#888"))[1]
        
                st.markdown(
                    f"<div style='background: linear-gradient(135deg, {color}22, {color}11);"
                    f"border-radius:12px; padding:20px; border:1px solid {color}44; text-align:center;'>"
                    f"<h3 style='color:{color}; margin:0;'>{s.name} Case</h3>"
                    f"<p style='font-size:32px; font-weight:700; margin:8px 0; color:#1E293B;'>${iv:,.2f}</p>"
                    f"<p style='color:#64748B; margin:0;'>WACC: {r.wacc_result.wacc:.1%} | MoS: {sc_mos:.1%}</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        
        
        # ──────────────────────────────────────────────────────────────────────
        # Sensitivity Heatmap
        # ──────────────────────────────────────────────────────────────────────
        
        st.markdown("### Sensitivity Analysis — WACC vs. Terminal Growth Rate")
        
        base_wacc_computed = result.wacc_result.wacc
        wacc_center = round(base_wacc_computed, 2)
        wacc_range = sorted(set([
            round(wacc_center - 0.02, 3),
            round(wacc_center - 0.01, 3),
            round(wacc_center, 3),
            round(wacc_center + 0.01, 3),
            round(wacc_center + 0.02, 3),
        ]))
        tgr_range = [0.015, 0.020, 0.025, 0.030, 0.035]
        
        sensitivity_df = run_sensitivity_analysis(dcf_inputs, wacc_range, tgr_range)
        
        # Build Plotly heatmap
        z_vals = sensitivity_df.values.tolist()
        x_labels = [str(c) for c in sensitivity_df.columns]
        y_labels = [str(r) for r in sensitivity_df.index]
        
        # Annotation text (formatted prices)
        annotations_text = []
        for row in z_vals:
            ann_row = []
            for val in row:
                if val != val:  # NaN
                    ann_row.append("N/A")
                else:
                    ann_row.append(f"${val:,.0f}")
            annotations_text.append(ann_row)
        
        fig = go.Figure(data=go.Heatmap(
            z=z_vals,
            x=x_labels,
            y=y_labels,
            text=annotations_text,
            texttemplate="%{text}",
            textfont={"size": 13, "color": "white"},
            colorscale=[
                [0.0, "#DC2626"],
                [0.3, "#F59E0B"],
                [0.5, "#FBBF24"],
                [0.7, "#22C55E"],
                [1.0, "#15803D"],
            ],
            colorbar=dict(
                title="Share Price",
                titleside="right",
                tickprefix="$",
            ),
            hovertemplate=(
                "WACC: %{y}<br>"
                "Terminal Growth: %{x}<br>"
                "Implied Price: %{text}<br>"
                "<extra></extra>"
            ),
        ))
        
        fig.update_layout(
            xaxis_title="Terminal Growth Rate",
            yaxis_title="WACC",
            yaxis=dict(autorange="reversed"),
            height=400,
            margin=dict(l=60, r=40, t=30, b=60),
            font=dict(family="Inter, sans-serif", size=12),
            plot_bgcolor="white",
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown(
            f"<p style='text-align:center; color:#94A3B8; font-size:12px;'>"
            f"Base case: WACC = {base_wacc_computed:.1%}, TGR = {tgr_dec:.1%}"
            f"</p>",
            unsafe_allow_html=True,
        )
        
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        
        
        # ──────────────────────────────────────────────────────────────────────
        # PDF Download
        # ──────────────────────────────────────────────────────────────────────
        
        st.markdown("### Export Report")
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = generate_pdf_report(
                ticker_data=data,
                dcf_result=result,
                scenarios=scenarios,
                sensitivity_df=sensitivity_df,
                output_dir=tmp_dir,
            )
        
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        
            st.download_button(
                label=f"Download {data.ticker} DCF Report (PDF)",
                data=pdf_bytes,
                file_name=f"{data.ticker}_DCF_Report.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        

with tab_manual:
    # Manual N-1 Solver
    # ──────────────────────────────────────────────────────────────────────
    
    st.markdown("### Manual N-1 Variable Solver")
    st.markdown(
        "<p style='color:#64748B; font-size:13px; margin-bottom:16px;'>"
        "Enter explicit cash flows and assumptions below.  Select the "
        "<b>target variable</b> to solve for — the solver computes it "
        "automatically whenever you change an input.</p>",
        unsafe_allow_html=True,
    )
    
    # ── Dropdown: choose the solve target ────────────────────────────────
    _SOLVE_OPTIONS = {
        "Implied Enterprise Value (PV)":  "manual_target_pv",
        "Initial Outlay (CF0)":           "manual_cf0",
        "Discount Rate (WACC)":           "manual_wacc",
        "Terminal Growth Rate (g)":       "manual_g",
    }
    _SOLVE_LABELS = list(_SOLVE_OPTIONS.keys())
    _SOLVE_KEYS   = list(_SOLVE_OPTIONS.values())
    
    
    def _on_solve_target_change() -> None:
        """Update manual_solve_for when the selectbox changes, then re-solve."""
        selected_label = st.session_state["_manual_solve_dropdown"]
        st.session_state["manual_solve_for"] = _SOLVE_OPTIONS[selected_label]
        run_valuation_solver()
    
    
    # Derive the current index from session_state
    _current_solve_key = st.session_state["manual_solve_for"]
    _current_idx = _SOLVE_KEYS.index(_current_solve_key) if _current_solve_key in _SOLVE_KEYS else 0
    
    st.selectbox(
        "Target Variable to Solve For",
        options=_SOLVE_LABELS,
        index=_current_idx,
        key="_manual_solve_dropdown",
        on_change=_on_solve_target_change,
        help="The selected variable will be computed from the others.",
    )
    
    # ── Convenience: which keys are disabled ─────────────────────────────
    _solving = st.session_state["manual_solve_for"]
    
    
    # ── Solved result metric card ────────────────────────────────────────
    _result = st.session_state.get("manual_solver_result")
    _error  = st.session_state.get("manual_solver_error")
    
    if _error:
        st.error(f"Solver Error: {_error}")
    elif _result:
        _solved_name = _result["variable"]
        _solved_val  = _result["value"]
        # Format label from the options dict (reverse-lookup)
        _display_name = next(
            (lbl for lbl, k in _SOLVE_OPTIONS.items() if _SOLVE_TARGET_MAP.get(k) == _solved_name),
            _solved_name,
        )
        # Choose format
        if _solved_name in ("wacc", "perpetual_growth"):
            _display_val = f"{_solved_val:.4%}"
        else:
            _display_val = f"${_solved_val:,.2f}"
    
        st.markdown(
            f"<div class='metric-card' style='margin-bottom:20px;'>"
            f"<div class='value'>{_display_val}</div>"
            f"<div class='label'>Solved: {_display_name}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    
    # ── Row 1: Timing parameters ────────────────────────────────────────
    st.markdown("#### Timing & Structure")
    t_c1, t_c2, t_c3 = st.columns(3)
    
    with t_c1:
        st.number_input(
            "Projection Periods (N)",
            min_value=1, max_value=30, step=1,
            key="manual_n",
            on_change=run_valuation_solver,
            help="Number of explicit cash flow periods.",
        )
    
    with t_c2:
        st.number_input(
            "Compounding Frequency (m)",
            min_value=1, max_value=365, step=1,
            key="manual_m",
            on_change=run_valuation_solver,
            help="1 = annual, 2 = semi-annual, 12 = monthly.",
        )
    
    with t_c3:
        st.checkbox(
            "Mid-Year Convention",
            key="manual_mid_year",
            on_change=run_valuation_solver,
            help="Discount to midpoint of each period instead of end.",
        )
    
    # ── Row 2: Rate variables ───────────────────────────────────────────
    st.markdown("#### Rates & Targets")
    st.caption("Type values in industry format:  `14%`  `0.14`  `$1M`  `500K`  `-$15,000`")
    r_c1, r_c2, r_c3, r_c4 = st.columns(4)

    def _on_wacc_text():
        try:
            st.session_state["manual_wacc"] = _parse_rate(st.session_state["_wacc_text"])
        except ValueError:
            pass
        run_valuation_solver()

    def _on_g_text():
        try:
            st.session_state["manual_g"] = _parse_rate(st.session_state["_g_text"])
        except ValueError:
            pass
        run_valuation_solver()

    def _on_tpv_text():
        try:
            st.session_state["manual_target_pv"] = _parse_currency(st.session_state["_tpv_text"])
        except ValueError:
            pass
        run_valuation_solver()

    def _on_tnpv_text():
        try:
            st.session_state["manual_target_npv"] = _parse_currency(st.session_state["_tnpv_text"])
        except ValueError:
            pass
        run_valuation_solver()

    with r_c1:
        st.text_input(
            "WACC (Discount Rate)",
            value=_fmt_rate(st.session_state["manual_wacc"]),
            key="_wacc_text",
            disabled=(_solving == "manual_wacc"),
            on_change=_on_wacc_text,
            help="e.g. 10%, 0.10",
        )

    with r_c2:
        st.text_input(
            "Terminal Growth Rate (g)",
            value=_fmt_rate(st.session_state["manual_g"]),
            key="_g_text",
            disabled=(_solving == "manual_g"),
            on_change=_on_g_text,
            help="Also known as Perpetual Growth Rate (g). e.g. 2.5%, 0.025",
        )

    with r_c3:
        st.text_input(
            "Target PV",
            value=_fmt_currency(st.session_state["manual_target_pv"]),
            key="_tpv_text",
            disabled=(_solving == "manual_target_pv"),
            on_change=_on_tpv_text,
        )

    with r_c4:
        st.text_input(
            "Target NPV",
            value=_fmt_currency(st.session_state["manual_target_npv"]),
            key="_tnpv_text",
            on_change=_on_tnpv_text,
            help="Usually $0 when solving for IRR.",
        )

    # ── Row 3: CF0 & Terminal Value ──────────────────────────────────────
    st.markdown("#### Initial Outlay & Terminal Value")
    v_c1, v_c2 = st.columns(2)

    def _on_cf0_text():
        try:
            st.session_state["manual_cf0"] = _parse_currency(st.session_state["_cf0_text"])
        except ValueError:
            pass
        run_valuation_solver()

    def _on_tv_text():
        try:
            st.session_state["manual_tv"] = _parse_currency(st.session_state["_tv_text"])
        except ValueError:
            pass
        run_valuation_solver()

    with v_c1:
        st.text_input(
            "Initial Outlay (CF₀)",
            value=_fmt_currency(st.session_state["manual_cf0"]),
            key="_cf0_text",
            disabled=(_solving == "manual_cf0"),
            on_change=_on_cf0_text,
            help="e.g. -$1,000,000 or -1M",
        )

    with v_c2:
        st.text_input(
            "Terminal Value (at end of period N)",
            value=_fmt_currency(st.session_state["manual_tv"]),
            key="_tv_text",
            on_change=_on_tv_text,
            help="e.g. $500K, 500000, 0.5M",
        )
    
    # ── Row 4: Discrete cash flows ──────────────────────────────────────
    st.markdown("#### Discrete Cash Flows (CF₁ … CFₙ)")
    
    _n = int(st.session_state["manual_n"])
    _cfs = st.session_state["manual_cfs"]
    
    # Ensure the list has exactly N entries for the current period count
    if len(_cfs) < _n:
        _cfs.extend([0.0] * (_n - len(_cfs)))
        st.session_state["manual_cfs"] = _cfs
    elif len(_cfs) > _n:
        st.session_state["manual_cfs"] = _cfs[:_n]
        _cfs = st.session_state["manual_cfs"]
    
    # Render CF inputs in rows of 5
    _cf_cols_per_row = 5
    for row_start in range(0, _n, _cf_cols_per_row):
        row_end = min(row_start + _cf_cols_per_row, _n)
        cols = st.columns(row_end - row_start)
        for col_idx, period_idx in enumerate(range(row_start, row_end)):
            with cols[col_idx]:

                def _make_cf_callback(idx: int):
                    """Factory to capture idx by value (avoids late-binding bug)."""
                    def _cb():
                        try:
                            parsed = _parse_currency(st.session_state[f"_cf_input_{idx}"])
                            st.session_state["manual_cfs"][idx] = parsed
                        except ValueError:
                            pass
                        run_valuation_solver()
                    return _cb

                st.text_input(
                    f"CF{period_idx + 1}",
                    value=_fmt_currency(float(_cfs[period_idx])),
                    key=f"_cf_input_{period_idx}",
                    on_change=_make_cf_callback(period_idx),
                )
    
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    
    
    # ──────────────────────────────────────────────────────────────────────

st.markdown(
    "<p style='text-align:center; color:#94A3B8; font-size:11px; margin-top:24px;'>"
    "Built with Streamlit, Plotly, and ReportLab. "
    "Data from Yahoo Finance. Not financial advice.</p>",
    unsafe_allow_html=True,
)
