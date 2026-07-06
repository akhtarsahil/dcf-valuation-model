# app.py
"""
DCF Valuation Model — Application Entry Point.

Usage:
    python app.py AAPL          # Fetch live data and run DCF valuation
    python app.py MSFT          # Any valid Yahoo Finance ticker

Pulls live financial data via yfinance, builds assumptions from historical
actuals, runs the full DCF pipeline, and prints a formatted terminal report
including Intrinsic Value, Current Price, Margin of Safety, and a
valuation recommendation.
"""

from __future__ import annotations

import sys
from datetime import datetime

# Ensure UTF-8 output on Windows terminals (box-drawing chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


from utils.finance import fetch_ticker_data, TickerData
from models.wacc import WACCInputs
from models.forecasting import ForecastInputs
from models.dcf import DCFInputs, DCFResult, run_dcf
from models.valuation import run_scenario_analysis, run_sensitivity_analysis


# ──────────────────────────────────────────────────────────────────────
# Assumption builders — translate live data into model inputs
# ──────────────────────────────────────────────────────────────────────

# Market-level assumptions (analyst can override these)
DEFAULT_RISK_FREE_RATE = 0.043       # ~10-year U.S. Treasury yield
DEFAULT_EQUITY_RISK_PREMIUM = 0.055  # Damodaran long-run ERP estimate
DEFAULT_COST_OF_DEBT_PRETAX = 0.055  # BBB-rated corporate yield proxy
DEFAULT_TAX_RATE = 0.21             # U.S. federal statutory rate
DEFAULT_TERMINAL_GROWTH_RATE = 0.025 # ~nominal GDP growth


def _build_wacc_inputs(data: TickerData) -> WACCInputs:
    """Build WACC inputs from live market data.

    - Cost of Equity via CAPM using the company's actual beta.
    - Capital structure weights derived from market cap vs. total debt.
    """
    beta = max(data.beta, 0.5)  # Floor beta at 0.5 for defensive names

    # Capital structure from market values
    equity_mv = data.market_cap if data.market_cap > 0 else data.current_price * data.shares_outstanding
    debt_mv = max(data.total_debt, 0.0)
    total_capital = equity_mv + debt_mv

    if total_capital > 0:
        equity_ratio = equity_mv / total_capital
        debt_ratio = debt_mv / total_capital
    else:
        equity_ratio = 1.0
        debt_ratio = 0.0

    # Ensure ratios sum to exactly 1.0
    equity_ratio = round(equity_ratio, 10)
    debt_ratio = round(1.0 - equity_ratio, 10)

    return WACCInputs(
        risk_free_rate=DEFAULT_RISK_FREE_RATE,
        beta=beta,
        equity_risk_premium=DEFAULT_EQUITY_RISK_PREMIUM,
        cost_of_debt_pretax=DEFAULT_COST_OF_DEBT_PRETAX,
        tax_rate=DEFAULT_TAX_RATE,
        debt_ratio=debt_ratio,
        equity_ratio=equity_ratio,
    )


def _build_forecast_inputs(data: TickerData) -> ForecastInputs:
    """Build 5-year forecast assumptions from historical financial data.

    Revenue growth:
        - Uses the average of historical YoY growth rates as the Year-1 rate,
          then decays by ~20% per year to model growth deceleration.
        - Clamped between 2% and 40%.

    EBIT margin:
        - Starts from the latest actual EBIT margin and linearly converges
          toward a 20% long-run target over 5 years (mean reversion).

    Other drivers use sector-neutral defaults that the analyst can override.
    """
    n = 5

    # ── Revenue growth ───────────────────────────────────────────────
    if data.revenue_growth_rates:
        avg_growth = sum(data.revenue_growth_rates) / len(data.revenue_growth_rates)
    else:
        avg_growth = 0.08  # fallback

    # Clamp starting growth
    avg_growth = max(0.02, min(avg_growth, 0.40))

    # Decay growth ~20% each year toward a floor
    growth_rates = []
    g = avg_growth
    for _ in range(n):
        growth_rates.append(round(max(0.02, g), 4))
        g *= 0.80  # decelerate

    # ── EBIT margin (mean-revert toward 20%) ─────────────────────────
    current_margin = data.latest_ebit_margin
    if current_margin <= 0:
        current_margin = 0.15  # fallback for negative-EBIT companies
    target_margin = 0.20
    ebit_margins = []
    for i in range(n):
        weight = (i + 1) / n  # 0.2, 0.4, 0.6, 0.8, 1.0
        margin = current_margin + (target_margin - current_margin) * weight * 0.5
        ebit_margins.append(round(max(0.05, margin), 4))

    # ── Other drivers (sensible defaults) ────────────────────────────
    tax_rates = [DEFAULT_TAX_RATE] * n
    depreciation_pct = [0.03] * n       # 3% of revenue
    capex_pct = [0.05, 0.05, 0.04, 0.04, 0.04]  # moderating reinvestment
    nwc_pct = [0.08] * n                # 8% of incremental revenue

    return ForecastInputs(
        base_revenue=data.latest_revenue,
        revenue_growth_rates=growth_rates,
        ebit_margins=ebit_margins,
        tax_rates=tax_rates,
        depreciation_pct_of_rev=depreciation_pct,
        capex_pct_of_rev=capex_pct,
        nwc_pct_of_rev_change=nwc_pct,
    )


# ──────────────────────────────────────────────────────────────────────
# Formatted terminal output
# ──────────────────────────────────────────────────────────────────────

def _fmt_currency(val: float, billions: bool = False) -> str:
    """Format a number as currency. Use billions for large-cap figures."""
    if billions:
        return f"${val / 1e9:,.2f}B"
    if abs(val) >= 1e6:
        return f"${val / 1e6:,.1f}M"
    return f"${val:,.2f}"


def _fmt_pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def _print_report(data: TickerData, result: DCFResult) -> None:
    """Print a formatted DCF valuation report to the terminal."""
    w = result.wacc_result
    intrinsic = result.implied_share_price
    current = data.current_price

    # Margin of Safety = (Intrinsic − Current) / Intrinsic
    if intrinsic > 0:
        margin_of_safety = (intrinsic - current) / intrinsic
    else:
        margin_of_safety = -1.0

    if margin_of_safety > 0.15:
        recommendation = "[+] UNDERVALUED -- Intrinsic value exceeds market price"
        rec_color = "+"
    elif margin_of_safety > 0:
        recommendation = "[~] FAIRLY VALUED -- Slight upside; limited margin of safety"
        rec_color = "~"
    else:
        recommendation = "[-] OVERVALUED -- Market price exceeds intrinsic estimate"
        rec_color = "-"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    print()
    print("╔" + "═" * 62 + "╗")
    print("║" + f"  DCF VALUATION REPORT -- {data.company_name}".ljust(62) + "║")
    print("║" + f"  Ticker: {data.ticker}  |  {now}".ljust(62) + "║")
    print("╠" + "═" * 62 + "╣")

    # ── Key verdict ──────────────────────────────────────────────────
    print("║" + "".ljust(62) + "║")
    print("║" + f"  Intrinsic Value ............ ${intrinsic:>12,.2f} / share".ljust(62) + "║")
    print("║" + f"  Current Market Price ........ ${current:>12,.2f} / share".ljust(62) + "║")
    print("║" + f"  Margin of Safety ........... {margin_of_safety:>12.1%}".ljust(62) + "║")
    print("║" + "".ljust(62) + "║")
    print("║" + f"  {recommendation}".ljust(62) + "║")
    print("║" + "".ljust(62) + "║")

    # ── WACC breakdown ───────────────────────────────────────────────
    print("╠" + "═" * 62 + "╣")
    print("║" + "  WACC BREAKDOWN".ljust(62) + "║")
    print("╠" + "─" * 62 + "╣")
    print("║" + f"  Cost of Equity (CAPM) ....... {_fmt_pct(w.cost_of_equity):>10}".ljust(62) + "║")
    print("║" + f"    Rf={_fmt_pct(result.wacc_result.cost_of_equity - data.beta * DEFAULT_EQUITY_RISK_PREMIUM)}  β={data.beta:.2f}  ERP={_fmt_pct(DEFAULT_EQUITY_RISK_PREMIUM)}".ljust(62) + "║")
    print("║" + f"  Cost of Debt (after-tax) .... {_fmt_pct(w.cost_of_debt_aftertax):>10}".ljust(62) + "║")
    print("║" + f"  Equity / Debt Weight ........ {_fmt_pct(w.equity_ratio)} / {_fmt_pct(w.debt_ratio)}".ljust(62) + "║")
    print("║" + f"  >>> WACC .................... {_fmt_pct(w.wacc):>10}".ljust(62) + "║")

    # ── Forecast summary ─────────────────────────────────────────────
    print("╠" + "═" * 62 + "╣")
    print("║" + "  5-YEAR PROJECTED FREE CASH FLOWS".ljust(62) + "║")
    print("╠" + "─" * 62 + "╣")
    print("║" + f"  {'Yr':>3}  {'Revenue':>12}  {'EBIT':>10}  {'FCF':>10}  {'PV(FCF)':>10}".ljust(62) + "║")
    print("║" + f"  {'---':>3}  {'-------':>12}  {'----':>10}  {'---':>10}  {'-------':>10}".ljust(62) + "║")
    for dy in result.discounted_years:
        proj = result.forecast_result.projections[dy.year - 1]
        print("║" + f"  {dy.year:>3}  {_fmt_currency(proj.revenue):>12}  {_fmt_currency(proj.ebit):>10}  {_fmt_currency(dy.fcf):>10}  {_fmt_currency(dy.present_value_fcf):>10}".ljust(62) + "║")

    # ── Valuation bridge ─────────────────────────────────────────────
    print("╠" + "═" * 62 + "╣")
    print("║" + "  VALUATION BRIDGE".ljust(62) + "║")
    print("╠" + "─" * 62 + "╣")
    print("║" + f"  NPV of Projected FCFs ...... {_fmt_currency(result.npv_of_fcfs, True):>14}".ljust(62) + "║")
    print("║" + f"  Terminal Value .............. {_fmt_currency(result.terminal_value, True):>14}".ljust(62) + "║")
    print("║" + f"  PV of Terminal Value ........ {_fmt_currency(result.pv_of_terminal_value, True):>14}".ljust(62) + "║")
    print("║" + "".ljust(62) + "║")
    print("║" + f"  Enterprise Value ............ {_fmt_currency(result.enterprise_value, True):>14}".ljust(62) + "║")
    print("║" + f"  Less: Net Debt .............. {_fmt_currency(result.net_debt, True):>14}".ljust(62) + "║")
    print("║" + f"  Equity Value ................ {_fmt_currency(result.equity_value, True):>14}".ljust(62) + "║")
    print("║" + f"  Shares Outstanding .......... {data.shares_outstanding / 1e9:>11.2f}B".ljust(62) + "║")
    print("║" + "".ljust(62) + "║")
    print("║" + f"  >>> INTRINSIC VALUE ......... ${intrinsic:>12,.2f}".ljust(62) + "║")
    print("║" + f"  >>> MARKET PRICE ............ ${current:>12,.2f}".ljust(62) + "║")
    print("║" + f"  >>> MARGIN OF SAFETY ........ {margin_of_safety:>12.1%}".ljust(62) + "║")
    print("╚" + "═" * 62 + "╝")
    print()


def _print_scenarios(scenarios, current_price: float) -> None:
    """Print Bull / Base / Bear scenario comparison table."""
    W = 62
    print("╔" + "═" * W + "╗")
    print("║" + "  SCENARIO ANALYSIS (Bull / Base / Bear)".ljust(W) + "║")
    print("╠" + "═" * W + "╣")

    # Header
    hdr = f"  {'Scenario':<8} {'Intrinsic':>12} {'EV':>12} {'WACC':>8} {'MoS':>10}"
    div = f"  {'--------':<8} {'---------':>12} {'--':>12} {'----':>8} {'---':>10}"
    print("║" + hdr.ljust(W) + "║")
    print("║" + div.ljust(W) + "║")

    for s in scenarios:
        r = s.dcf_result
        iv = r.implied_share_price
        ev = r.enterprise_value
        wacc = r.wacc_result.wacc
        mos = (iv - current_price) / iv if iv > 0 else -1.0

        # Tag
        if s.name == "Bull":
            tag = "[+]"
        elif s.name == "Bear":
            tag = "[-]"
        else:
            tag = "[=]"

        line = (
            f"  {tag + ' ' + s.name:<8}"
            f" ${iv:>11,.2f}"
            f" {_fmt_currency(ev, True):>12}"
            f" {_fmt_pct(wacc):>8}"
            f" {mos:>9.1%}"
        )
        print("║" + line.ljust(W) + "║")

    print("║" + "".ljust(W) + "║")
    print("║" + f"  Current Market Price: ${current_price:>10,.2f}".ljust(W) + "║")
    print("╚" + "═" * W + "╝")
    print()


def _print_sensitivity(df, base_wacc: float, base_tgr: float) -> None:
    """Print the WACC x Terminal Growth Rate sensitivity matrix."""
    W = 62
    print("╔" + "═" * W + "╗")
    print("║" + "  SENSITIVITY MATRIX: Implied Share Price".ljust(W) + "║")
    print("║" + "  (WACC vs. Terminal Growth Rate)".ljust(W) + "║")
    print("╠" + "═" * W + "╣")

    # Column headers (TGR values)
    col_labels = list(df.columns)
    hdr = f"  {'WACC':<8}"
    for c in col_labels:
        hdr += f" {c:>9}"
    print("║" + hdr.ljust(W) + "║")

    sep = f"  {'--------':<8}"
    for _ in col_labels:
        sep += f" {'---------':>9}"
    print("║" + sep.ljust(W) + "║")

    # Data rows
    base_wacc_label = f"{base_wacc * 100:.1f}%"
    base_tgr_label = f"{base_tgr * 100:.1f}%"

    for wacc_label, row in df.iterrows():
        line = f"  {wacc_label:<8}"
        for tgr_label in col_labels:
            val = row[tgr_label]
            if str(wacc_label) == base_wacc_label and str(tgr_label) == base_tgr_label:
                cell = f"*${val:>6,.0f}*" if not (val != val) else "    N/A "
            else:
                cell = f" ${val:>7,.0f}" if not (val != val) else "     N/A"
            line += f" {cell:>9}"
        print("║" + line.ljust(W) + "║")

    print("║" + "".ljust(W) + "║")
    print("║" + "  * = current base-case assumptions".ljust(W) + "║")
    print("╚" + "═" * W + "╝")
    print()


# ──────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Parse CLI arguments and execute the DCF valuation."""
    if len(sys.argv) < 2:
        print("Usage: python app.py <TICKER>")
        print("       python app.py AAPL")
        print("       python app.py MSFT")
        sys.exit(1)

    symbol = sys.argv[1].upper()

    print(f"\n  Fetching live data for {symbol} ...")
    data = fetch_ticker_data(symbol)
    print(f"  > {data.company_name} -- ${data.current_price:,.2f} / share")
    print(f"  > Revenue: {_fmt_currency(data.latest_revenue, True)}  |  EBIT margin: {_fmt_pct(data.latest_ebit_margin)}")
    print(f"  > Net Debt: {_fmt_currency(data.net_debt, True)}  |  Beta: {data.beta:.2f}")
    print(f"  Building DCF model ...")

    # ── Assemble model inputs from live data ─────────────────────────
    wacc_inputs = _build_wacc_inputs(data)
    forecast_inputs = _build_forecast_inputs(data)

    dcf_inputs = DCFInputs(
        wacc_inputs=wacc_inputs,
        forecast_inputs=forecast_inputs,
        terminal_growth_rate=DEFAULT_TERMINAL_GROWTH_RATE,
        net_debt=data.net_debt,
        shares_outstanding=data.shares_outstanding,
    )

    # ── Run the DCF pipeline ─────────────────────────────────────────
    result = run_dcf(dcf_inputs)

    # ── Output: Base report ──────────────────────────────────────────
    _print_report(data, result)

    # ── Output: Scenario analysis ────────────────────────────────────
    print("  Running scenario analysis (Bull / Base / Bear) ...")
    scenarios = run_scenario_analysis(dcf_inputs)
    _print_scenarios(scenarios, data.current_price)

    # ── Output: Sensitivity matrix ───────────────────────────────────
    print("  Running sensitivity analysis ...")
    base_wacc = result.wacc_result.wacc
    # Build a WACC range centered around the computed base WACC
    wacc_center = round(base_wacc, 2)
    wacc_range = sorted(set([
        round(wacc_center - 0.02, 3),
        round(wacc_center - 0.01, 3),
        round(wacc_center, 3),
        round(wacc_center + 0.01, 3),
        round(wacc_center + 0.02, 3),
    ]))
    tgr_range = [0.015, 0.020, 0.025, 0.030, 0.035]
    sensitivity_df = run_sensitivity_analysis(dcf_inputs, wacc_range, tgr_range)
    _print_sensitivity(sensitivity_df, base_wacc, DEFAULT_TERMINAL_GROWTH_RATE)


if __name__ == "__main__":
    main()
