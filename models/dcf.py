# models/dcf.py
"""
Discounted Cash Flow (DCF) engine.

Orchestrates the full DCF valuation pipeline by importing and composing
the WACC calculator and the forecasting engine:

  1. Compute WACC dynamically via models.wacc.
  2. Build projected free cash flows via models.forecasting.
  3. Discount each year's FCF to present value.
  4. Estimate terminal value via the Gordon Growth Model.
  5. Sum to Enterprise Value, bridge to Equity Value, derive Implied Share Price.

Usage:
    from models.dcf import DCFInputs, run_dcf

    result = run_dcf(DCFInputs(
        wacc_inputs=WACCInputs(...),
        forecast_inputs=ForecastInputs(...),
        terminal_growth_rate=0.025,
        net_debt=120_000,
        shares_outstanding=10_000,
    ))

    print(f"Implied share price: ${result.implied_share_price:,.2f}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from models.wacc import WACCInputs, WACCResult, calculate_wacc
from models.forecasting import ForecastInputs, ForecastResult, ProjectedYear, build_forecast


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────


@dataclass
class DCFInputs:
    """Top-level inputs for the DCF valuation.

    Attributes:
        wacc_inputs:           Inputs for the WACC calculator (CAPM + capital structure).
        forecast_inputs:       Inputs for the 5-year financial forecast.
        terminal_growth_rate:  Perpetuity growth rate applied to the last year's FCF
                               in the Gordon Growth Model.  Must be strictly less than WACC.
        net_debt:              Total Debt − Cash & Equivalents.  Subtracted from Enterprise
                               Value to arrive at Equity Value.
        shares_outstanding:    Fully diluted share count for per-share price computation.
    """

    wacc_inputs: WACCInputs
    forecast_inputs: ForecastInputs
    terminal_growth_rate: float
    net_debt: float
    shares_outstanding: float

    def __post_init__(self) -> None:
        if self.shares_outstanding <= 0:
            raise ValueError(
                f"shares_outstanding must be positive, got {self.shares_outstanding}"
            )
        if self.terminal_growth_rate < 0:
            raise ValueError(
                f"terminal_growth_rate must be non-negative, got {self.terminal_growth_rate}"
            )


@dataclass
class ManualDCFInputs:
    """Explicit numerical-array DCF inputs that bypass ForecastInputs.

    This dataclass accepts pre-computed cash flows directly (e.g. from a
    spreadsheet or external model) rather than deriving them from operating
    drivers like revenue growth and EBIT margins.

    Exactly ONE of the four "solvable" fields must be set to None,
    indicating that it is the unknown variable to be solved for:
        - initial_outlay_cf0  (solve for the break-even initial investment)
        - target_pv           (solve for the present value of cash flows)
        - wacc                (solve for the implied discount rate / IRR)
        - perpetual_growth    (solve for the implied terminal growth rate)

    Attributes:
        projection_period_n:   Number of explicit projection periods (N).
        compounding_m:         Compounding frequency per period.
                               1 = annual, 2 = semi-annual, 12 = monthly.
        mid_year_convention:   If True, discount each period's cash flow to
                               the midpoint (t − 0.5) rather than end-of-period.
        initial_outlay_cf0:    The initial cash outflow at t=0 (typically negative).
                               Set to None to solve for the break-even outlay.
        cash_flows:            Explicit list of free cash flows for periods 1..N.
                               Length must equal projection_period_n.
        terminal_value:        Explicit terminal value at the end of period N.
                               Set to None if no terminal value applies.
        wacc:                  Discount rate (as a decimal).  Set to None to
                               back-solve for the implied WACC / IRR.
        perpetual_growth:      Perpetuity growth rate applied beyond period N.
                               Set to None to back-solve for the implied rate.
        target_npv:            Target Net Present Value (default 0.0).  Used when
                               solving for the unknown variable (e.g. NPV = 0 for IRR).
        target_pv:             Target Present Value of future cash flows.
                               Set to None to solve for PV.
        net_debt:              Total Debt − Cash, subtracted from Enterprise Value.
        shares_outstanding:    Fully diluted share count for per-share computation.
    """

    projection_period_n: int
    compounding_m: int
    mid_year_convention: bool
    initial_outlay_cf0: Optional[float]
    cash_flows: List[float]
    terminal_value: Optional[float]
    wacc: Optional[float]
    perpetual_growth: Optional[float]
    target_npv: float = 0.0
    target_pv: Optional[float] = None
    net_debt: float = 0.0
    shares_outstanding: float = 1.0

    def __post_init__(self) -> None:
        # ── Validate cash_flows length ───────────────────────────────
        if len(self.cash_flows) != self.projection_period_n:
            raise ValueError(
                f"cash_flows length ({len(self.cash_flows)}) must equal "
                f"projection_period_n ({self.projection_period_n})."
            )

        # ── Validate compounding frequency ───────────────────────────
        if self.compounding_m < 1:
            raise ValueError(
                f"compounding_m must be >= 1, got {self.compounding_m}."
            )

        # ── Validate projection period ───────────────────────────────
        if self.projection_period_n < 1:
            raise ValueError(
                f"projection_period_n must be >= 1, got {self.projection_period_n}."
            )

        # ── Validate shares outstanding ──────────────────────────────
        if self.shares_outstanding <= 0:
            raise ValueError(
                f"shares_outstanding must be positive, got {self.shares_outstanding}."
            )

        # ── Exactly one solvable variable must be None ───────────────
        solvable_fields = {
            "initial_outlay_cf0": self.initial_outlay_cf0,
            "target_pv": self.target_pv,
            "wacc": self.wacc,
            "perpetual_growth": self.perpetual_growth,
        }
        none_fields = [name for name, val in solvable_fields.items() if val is None]

        if len(none_fields) == 0:
            raise ValueError(
                "Exactly one of (initial_outlay_cf0, target_pv, wacc, "
                "perpetual_growth) must be None to indicate the solve-for "
                "variable, but all four are specified."
            )
        if len(none_fields) > 1:
            raise ValueError(
                f"Exactly one of (initial_outlay_cf0, target_pv, wacc, "
                f"perpetual_growth) must be None, but {len(none_fields)} "
                f"are None: {', '.join(none_fields)}."
            )


@dataclass
class DiscountedYear:
    """A single projected year enriched with DCF math.

    Attributes:
        year:              Projection year (1-indexed).
        fcf:               Unlevered Free Cash Flow for this year.
        discount_factor:   1 / (1 + WACC)^year.
        present_value_fcf: FCF × discount_factor.
    """

    year: int
    fcf: float
    discount_factor: float
    present_value_fcf: float


@dataclass
class DCFResult:
    """Complete output of the DCF valuation.

    Contains every intermediate result so downstream consumers (reports,
    dashboards, sensitivity analysis) can inspect and audit the full chain.

    Attributes:
        wacc_result:           Detailed WACC computation breakdown.
        forecast_result:       Full year-by-year financial projections.
        discounted_years:      FCF present values per projection year.
        terminal_year_fcf:     Last-year FCF used as basis for terminal value.
        terminal_growth_rate:  Perpetuity growth rate (g).
        terminal_value:        Gordon Growth Model TV = FCF_N × (1+g) / (WACC − g).
        pv_of_terminal_value:  Terminal Value discounted to present.
        npv_of_fcfs:           Sum of PV(FCF) across all projection years.
        enterprise_value:      NPV of FCFs + PV of Terminal Value.
        net_debt:              Total Debt − Cash.
        equity_value:          Enterprise Value − Net Debt.
        shares_outstanding:    Fully diluted share count.
        implied_share_price:   Equity Value / Shares Outstanding.
    """

    wacc_result: WACCResult
    forecast_result: ForecastResult
    discounted_years: List[DiscountedYear] = field(default_factory=list)

    terminal_year_fcf: float = 0.0
    terminal_growth_rate: float = 0.0
    terminal_value: float = 0.0
    pv_of_terminal_value: float = 0.0

    npv_of_fcfs: float = 0.0
    enterprise_value: float = 0.0
    net_debt: float = 0.0
    equity_value: float = 0.0
    shares_outstanding: float = 0.0
    implied_share_price: float = 0.0


# ──────────────────────────────────────────────────────────────────────
# Core engine
# ──────────────────────────────────────────────────────────────────────


def _discount_factor(wacc: float, year: int) -> float:
    """End-of-year discount factor: 1 / (1 + WACC)^year."""
    return 1.0 / ((1.0 + wacc) ** year)


def _terminal_value_gordon(
    terminal_fcf: float,
    terminal_growth_rate: float,
    wacc: float,
) -> float:
    """Gordon Growth Model terminal value.

    TV = FCF_N × (1 + g) / (WACC − g)

    Raises ValueError if WACC ≤ terminal growth rate (model diverges).
    """
    if wacc <= terminal_growth_rate:
        raise ValueError(
            f"WACC ({wacc:.4%}) must exceed the terminal growth rate "
            f"({terminal_growth_rate:.4%}) for the Gordon Growth Model to converge."
        )
    terminal_year_cf = terminal_fcf * (1.0 + terminal_growth_rate)
    return terminal_year_cf / (wacc - terminal_growth_rate)


def run_dcf(inputs: DCFInputs) -> DCFResult:
    """Execute the full DCF valuation pipeline.

    Steps:
        1. Compute WACC dynamically from CAPM and capital-structure inputs.
        2. Build the multi-year FCF forecast.
        3. Discount each projected FCF to present value using the computed WACC.
        4. Estimate Terminal Value via the Gordon Growth Model.
        5. Discount Terminal Value to present.
        6. Sum to Enterprise Value → subtract Net Debt → Equity Value → Share Price.

    Args:
        inputs: A fully-specified DCFInputs dataclass.

    Returns:
        DCFResult with every intermediate value populated.
    """

    # ── Step 1: WACC ─────────────────────────────────────────────────
    wacc_result = calculate_wacc(inputs.wacc_inputs)
    wacc = wacc_result.wacc

    # ── Step 2: Forecast ─────────────────────────────────────────────
    forecast_result = build_forecast(inputs.forecast_inputs)

    # ── Step 3: Discount projected FCFs ──────────────────────────────
    discounted_years: List[DiscountedYear] = []
    npv_of_fcfs = 0.0

    for proj in forecast_result.projections:
        df = _discount_factor(wacc, proj.year)
        pv = proj.fcf * df
        npv_of_fcfs += pv

        discounted_years.append(
            DiscountedYear(
                year=proj.year,
                fcf=proj.fcf,
                discount_factor=df,
                present_value_fcf=pv,
            )
        )

    # ── Step 4: Terminal value ───────────────────────────────────────
    terminal_year_fcf = forecast_result.terminal_fcf
    terminal_value = _terminal_value_gordon(
        terminal_year_fcf,
        inputs.terminal_growth_rate,
        wacc,
    )

    # ── Step 5: Discount terminal value to present ───────────────────
    last_year = inputs.forecast_inputs.projection_years
    tv_discount_factor = _discount_factor(wacc, last_year)
    pv_of_terminal_value = terminal_value * tv_discount_factor

    # ── Step 6: Valuation bridge ─────────────────────────────────────
    enterprise_value = npv_of_fcfs + pv_of_terminal_value
    equity_value = enterprise_value - inputs.net_debt
    implied_share_price = max(0.0, equity_value / inputs.shares_outstanding)

    return DCFResult(
        wacc_result=wacc_result,
        forecast_result=forecast_result,
        discounted_years=discounted_years,
        terminal_year_fcf=terminal_year_fcf,
        terminal_growth_rate=inputs.terminal_growth_rate,
        terminal_value=terminal_value,
        pv_of_terminal_value=pv_of_terminal_value,
        npv_of_fcfs=npv_of_fcfs,
        enterprise_value=enterprise_value,
        net_debt=inputs.net_debt,
        equity_value=equity_value,
        shares_outstanding=inputs.shares_outstanding,
        implied_share_price=implied_share_price,
    )
