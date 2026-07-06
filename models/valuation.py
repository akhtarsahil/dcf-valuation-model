# models/valuation.py
"""
Valuation scenario and sensitivity analysis module.

Provides two key analytical tools on top of the core DCF engine:

  1. Scenario Analysis — runs the DCF under Bull, Base, and Bear cases
     with distinct revenue growth, operating margin, and WACC assumptions.

  2. Sensitivity Analysis — computes a matrix of implied share prices
     across a grid of WACC and terminal growth rate values, returned
     as a pandas DataFrame for easy display and export.

Usage:
    from models.valuation import run_scenario_analysis, run_sensitivity_analysis

    scenarios = run_scenario_analysis(base_dcf_inputs)
    sensitivity_df = run_sensitivity_analysis(base_dcf_inputs)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Dict

import pandas as pd

from models.wacc import WACCInputs
from models.forecasting import ForecastInputs
from models.dcf import DCFInputs, DCFResult, run_dcf


# ──────────────────────────────────────────────────────────────────────
# Scenario Analysis
# ──────────────────────────────────────────────────────────────────────


@dataclass
class ScenarioResult:
    """Result of a single scenario run.

    Attributes:
        name:                Scenario label (e.g. "Bull", "Base", "Bear").
        revenue_growth_adj:  Multiplier applied to base revenue growth rates.
        margin_adj:          Additive adjustment to EBIT margins (e.g. +0.03).
        wacc_adj:            Additive adjustment to WACC inputs (applied via
                             the equity risk premium to shift the discount rate).
        dcf_result:          Full DCF output for this scenario.
    """

    name: str
    revenue_growth_adj: float
    margin_adj: float
    wacc_adj: float
    dcf_result: DCFResult


def _adjust_inputs_for_scenario(
    base_inputs: DCFInputs,
    growth_multiplier: float,
    margin_delta: float,
    wacc_delta: float,
    tgr_delta: float,
) -> DCFInputs:
    """Create a modified copy of DCFInputs for a given scenario.

    Args:
        base_inputs:       The base-case DCFInputs to clone and modify.
        growth_multiplier: Factor applied to each year's revenue growth rate
                           (e.g. 1.3 = 30% higher growth).
        margin_delta:      Additive shift to each year's EBIT margin
                           (e.g. +0.03 = +3 percentage points).
        wacc_delta:        Additive shift to the equity risk premium,
                           which flows through CAPM into WACC
                           (e.g. -0.015 = lower discount rate for bull case).
        tgr_delta:         Additive shift to the terminal growth rate.

    Returns:
        A new DCFInputs with adjusted assumptions.
    """
    # Deep-copy to avoid mutating the original
    fi = base_inputs.forecast_inputs
    new_growth = [
        round(max(0.005, g * growth_multiplier), 4)
        for g in fi.revenue_growth_rates
    ]
    new_margins = [
        round(max(0.05, m + margin_delta), 4)
        for m in fi.ebit_margins
    ]

    new_forecast = ForecastInputs(
        base_revenue=fi.base_revenue,
        revenue_growth_rates=new_growth,
        ebit_margins=new_margins,
        tax_rates=list(fi.tax_rates),
        depreciation_pct_of_rev=list(fi.depreciation_pct_of_rev),
        capex_pct_of_rev=list(fi.capex_pct_of_rev),
        nwc_pct_of_rev_change=list(fi.nwc_pct_of_rev_change),
        projection_years=fi.projection_years,
    )

    wi = base_inputs.wacc_inputs
    new_wacc = WACCInputs(
        risk_free_rate=wi.risk_free_rate,
        beta=wi.beta,
        equity_risk_premium=max(0.01, wi.equity_risk_premium + wacc_delta),
        cost_of_debt_pretax=wi.cost_of_debt_pretax,
        tax_rate=wi.tax_rate,
        debt_ratio=wi.debt_ratio,
        equity_ratio=wi.equity_ratio,
    )

    new_tgr = max(0.005, min(base_inputs.terminal_growth_rate + tgr_delta, 0.05))

    return DCFInputs(
        wacc_inputs=new_wacc,
        forecast_inputs=new_forecast,
        terminal_growth_rate=new_tgr,
        net_debt=base_inputs.net_debt,
        shares_outstanding=base_inputs.shares_outstanding,
    )


# Scenario definitions: (name, growth_mult, margin_delta, wacc_delta, tgr_delta)
_SCENARIO_SPECS = [
    ("Bull",  1.30,  +0.03, -0.015, +0.005),
    ("Base",  1.00,   0.00,  0.000,  0.000),
    ("Bear",  0.65,  -0.04, +0.020, -0.005),
]


def run_scenario_analysis(base_inputs: DCFInputs) -> List[ScenarioResult]:
    """Execute the DCF model under Bull, Base, and Bear scenarios.

    Scenario adjustments relative to the base case:

    | Scenario | Revenue Growth | EBIT Margin | WACC (via ERP) | Terminal Growth |
    |----------|---------------|-------------|----------------|-----------------|
    | Bull     | +30%          | +3pp        | -1.5pp         | +0.5pp          |
    | Base     | (unchanged)   | (unchanged) | (unchanged)    | (unchanged)     |
    | Bear     | -35%          | -4pp        | +2.0pp         | -0.5pp          |

    Args:
        base_inputs: The base-case DCFInputs (typically derived from live data).

    Returns:
        A list of three ScenarioResult objects (Bull, Base, Bear).
    """
    results: List[ScenarioResult] = []

    for name, g_mult, m_delta, w_delta, tgr_delta in _SCENARIO_SPECS:
        adjusted = _adjust_inputs_for_scenario(
            base_inputs, g_mult, m_delta, w_delta, tgr_delta
        )
        dcf_result = run_dcf(adjusted)

        results.append(
            ScenarioResult(
                name=name,
                revenue_growth_adj=g_mult,
                margin_adj=m_delta,
                wacc_adj=w_delta,
                dcf_result=dcf_result,
            )
        )

    return results


# ──────────────────────────────────────────────────────────────────────
# Sensitivity Analysis
# ──────────────────────────────────────────────────────────────────────


def run_sensitivity_analysis(
    base_inputs: DCFInputs,
    wacc_range: List[float] | None = None,
    tgr_range: List[float] | None = None,
) -> pd.DataFrame:
    """Compute implied share price across a WACC x Terminal Growth Rate matrix.

    For each (WACC, TGR) pair, the function overrides the discount rate
    and terminal growth rate in the base inputs, runs the full DCF, and
    records the implied share price.

    Args:
        base_inputs: The base-case DCFInputs.
        wacc_range:  List of WACC values to test (as decimals).
                     Defaults to [0.08, 0.09, 0.10, 0.11, 0.12].
        tgr_range:   List of terminal growth rates to test (as decimals).
                     Defaults to [0.02, 0.025, 0.03, 0.035, 0.04].

    Returns:
        A pandas DataFrame where:
          - Rows are WACC values (formatted as "8.0%", "9.0%", etc.)
          - Columns are TGR values (formatted similarly)
          - Cell values are implied share prices (floats)
    """
    if wacc_range is None:
        wacc_range = [0.08, 0.09, 0.10, 0.11, 0.12]
    if tgr_range is None:
        tgr_range = [0.020, 0.025, 0.030, 0.035, 0.040]

    # Build the forecast once — it doesn't change across the grid
    fi = base_inputs.forecast_inputs

    matrix: Dict[str, Dict[str, float]] = {}

    for wacc_val in wacc_range:
        row_label = f"{wacc_val * 100:.1f}%"
        matrix[row_label] = {}

        for tgr_val in tgr_range:
            col_label = f"{tgr_val * 100:.1f}%"

            # Skip invalid combinations where WACC <= TGR
            if wacc_val <= tgr_val:
                matrix[row_label][col_label] = float("nan")
                continue

            # Override WACC by adjusting the ERP so that the resulting
            # WACC lands on the target value.  We solve for the ERP
            # that produces the desired WACC given fixed Rf, beta,
            # Kd, and capital structure weights.
            wi = base_inputs.wacc_inputs
            kd_at = wi.cost_of_debt_pretax * (1.0 - wi.tax_rate)
            # wacc_target = equity_ratio * (Rf + beta * ERP_new) + debt_ratio * kd_at
            # => ERP_new = (wacc_target - debt_ratio * kd_at - equity_ratio * Rf) / (equity_ratio * beta)
            if wi.equity_ratio * wi.beta > 0:
                erp_needed = (
                    wacc_val - wi.debt_ratio * kd_at - wi.equity_ratio * wi.risk_free_rate
                ) / (wi.equity_ratio * wi.beta)
                erp_needed = max(0.01, erp_needed)
            else:
                erp_needed = wi.equity_risk_premium

            new_wacc_inputs = WACCInputs(
                risk_free_rate=wi.risk_free_rate,
                beta=wi.beta,
                equity_risk_premium=erp_needed,
                cost_of_debt_pretax=wi.cost_of_debt_pretax,
                tax_rate=wi.tax_rate,
                debt_ratio=wi.debt_ratio,
                equity_ratio=wi.equity_ratio,
            )

            new_dcf_inputs = DCFInputs(
                wacc_inputs=new_wacc_inputs,
                forecast_inputs=ForecastInputs(
                    base_revenue=fi.base_revenue,
                    revenue_growth_rates=list(fi.revenue_growth_rates),
                    ebit_margins=list(fi.ebit_margins),
                    tax_rates=list(fi.tax_rates),
                    depreciation_pct_of_rev=list(fi.depreciation_pct_of_rev),
                    capex_pct_of_rev=list(fi.capex_pct_of_rev),
                    nwc_pct_of_rev_change=list(fi.nwc_pct_of_rev_change),
                    projection_years=fi.projection_years,
                ),
                terminal_growth_rate=tgr_val,
                net_debt=base_inputs.net_debt,
                shares_outstanding=base_inputs.shares_outstanding,
            )

            result = run_dcf(new_dcf_inputs)
            matrix[row_label][col_label] = round(result.implied_share_price, 2)

    df = pd.DataFrame(matrix).T
    df.index.name = "WACC"
    df.columns.name = "Terminal Growth"
    return df
