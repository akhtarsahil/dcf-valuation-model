"""Quick integration test — runs the full DCF pipeline and prints results."""

from models.wacc import WACCInputs, calculate_wacc
from models.forecasting import ForecastInputs, build_forecast
from models.dcf import DCFInputs, run_dcf

# ── Build inputs ──
wacc_in = WACCInputs(
    risk_free_rate=0.043,
    beta=1.15,
    equity_risk_premium=0.055,
    cost_of_debt_pretax=0.05,
    tax_rate=0.21,
    debt_ratio=0.30,
    equity_ratio=0.70,
)

forecast_in = ForecastInputs(
    base_revenue=100_000,
    revenue_growth_rates=[0.20, 0.15, 0.12, 0.10, 0.08],
    ebit_margins=          [0.25, 0.27, 0.28, 0.30, 0.30],
    tax_rates=             [0.21, 0.21, 0.21, 0.21, 0.21],
    depreciation_pct_of_rev=[0.03, 0.03, 0.03, 0.02, 0.02],
    capex_pct_of_rev=       [0.05, 0.05, 0.04, 0.04, 0.04],
    nwc_pct_of_rev_change=  [0.10, 0.10, 0.08, 0.08, 0.08],
)

dcf_in = DCFInputs(
    wacc_inputs=wacc_in,
    forecast_inputs=forecast_in,
    terminal_growth_rate=0.025,
    net_debt=50_000,
    shares_outstanding=1_000,
)

# ── Run ──
result = run_dcf(dcf_in)
w = result.wacc_result

print("=" * 60)
print("           WACC CALCULATION")
print("=" * 60)
print(f"  Cost of Equity (CAPM) ......... {w.cost_of_equity:.2%}")
print(f"  Cost of Debt (pre-tax) ........ {w.cost_of_debt_pretax:.2%}")
print(f"  Cost of Debt (after-tax) ...... {w.cost_of_debt_aftertax:.2%}")
print(f"  Equity Weight ................. {w.equity_ratio:.0%}")
print(f"  Debt Weight ................... {w.debt_ratio:.0%}")
print(f"  >>> WACC ...................... {w.wacc:.2%}")
print()
print("=" * 60)
print("           5-YEAR FCF PROJECTION")
print("=" * 60)
header = f"  {'Yr':>3}  {'Revenue':>12}  {'EBIT':>10}  {'NOPAT':>10}  {'FCF':>10}  {'PV(FCF)':>10}"
divider = f"  {'---':>3}  {'-------':>12}  {'----':>10}  {'-----':>10}  {'---':>10}  {'-------':>10}"
print(header)
print(divider)
for dy in result.discounted_years:
    proj = result.forecast_result.projections[dy.year - 1]
    print(
        f"  {dy.year:>3}"
        f"  ${proj.revenue:>11,.0f}"
        f"  ${proj.ebit:>9,.0f}"
        f"  ${proj.nopat:>9,.0f}"
        f"  ${dy.fcf:>9,.0f}"
        f"  ${dy.present_value_fcf:>9,.0f}"
    )
print()
print("=" * 60)
print("           VALUATION SUMMARY")
print("=" * 60)
print(f"  NPV of Projected FCFs ........ ${result.npv_of_fcfs:>12,.0f}")
print(f"  Terminal Value ................ ${result.terminal_value:>12,.0f}")
print(f"  PV of Terminal Value .......... ${result.pv_of_terminal_value:>12,.0f}")
print(f"  Enterprise Value .............. ${result.enterprise_value:>12,.0f}")
print(f"  Less: Net Debt ................ (${result.net_debt:>11,.0f})")
print(f"  Equity Value .................. ${result.equity_value:>12,.0f}")
print(f"  Shares Outstanding ............ {result.shares_outstanding:>12,.0f}")
print(f"  >>> Implied Share Price ....... ${result.implied_share_price:>12,.2f}")
print("=" * 60)
