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
from models.dcf import DCFInputs, DCFResult, run_dcf
from models.valuation import run_scenario_analysis, run_sensitivity_analysis
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
        min_value=0.0, max_value=0.40, value=0.08,
        step=0.01, format="%.0f%%",
        help="Year-1 revenue growth rate. Decays ~20% per year.",
    )

    wacc_val = st.slider(
        "WACC (Discount Rate)",
        min_value=0.05, max_value=0.18, value=0.10,
        step=0.005, format="%.1f%%",
        help="Weighted average cost of capital used to discount FCFs.",
    )

    terminal_growth = st.slider(
        "Terminal Growth Rate",
        min_value=0.01, max_value=0.05, value=0.025,
        step=0.005, format="%.1f%%",
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
    st.markdown(
        "Enter a **ticker symbol** in the sidebar and click "
        "**Fetch Live Data** to begin."
    )
    st.stop()

if st.session_state.get("fetch_error"):
    st.error(f"Failed to fetch data: {st.session_state['fetch_error']}")
    st.stop()

data: TickerData = st.session_state["ticker_data"]


# ──────────────────────────────────────────────────────────────────────
# Run DCF with current slider values
# ──────────────────────────────────────────────────────────────────────

wacc_inputs = _build_wacc_inputs(data, wacc_override=wacc_val)
forecast_inputs = _build_forecast_inputs(
    data, growth_override=growth_rate, n_years=forecast_years,
)

dcf_inputs = DCFInputs(
    wacc_inputs=wacc_inputs,
    forecast_inputs=forecast_inputs,
    terminal_growth_rate=terminal_growth,
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
    f"Base case: WACC = {base_wacc_computed:.1%}, TGR = {terminal_growth:.1%}"
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

st.markdown(
    "<p style='text-align:center; color:#94A3B8; font-size:11px; margin-top:24px;'>"
    "Built with Streamlit, Plotly, and ReportLab. "
    "Data from Yahoo Finance. Not financial advice.</p>",
    unsafe_allow_html=True,
)
