# models/forecasting.py
"""
Financial statement forecasting module.

Projects the next 5 years of financial performance with independent,
per-year assumptions for each key driver:

  - Revenue          (base amount + year-by-year growth rates)
  - EBIT Margin      (year-by-year operating margin targets)
  - Tax Rate         (year-by-year effective tax rates)
  - Depreciation     (as a percentage of revenue, per year)
  - CapEx            (as a percentage of revenue, per year)
  - Working Capital  (change in NWC as a percentage of revenue change, per year)

Each driver accepts a list of 5 floats so the analyst can model margin
expansion, tax-law changes, reinvestment ramp-downs, and working-capital
efficiency improvements independently across the projection horizon.

Usage:
    from models.forecasting import ForecastInputs, build_forecast

    inputs = ForecastInputs(
        base_revenue=500_000,
        revenue_growth_rates=[0.20, 0.15, 0.12, 0.10, 0.08],
        ebit_margins=[0.25, 0.27, 0.28, 0.30, 0.30],
        tax_rates=[0.21, 0.21, 0.21, 0.21, 0.21],
        depreciation_pct_of_rev=[0.03, 0.03, 0.03, 0.02, 0.02],
        capex_pct_of_rev=[0.05, 0.05, 0.04, 0.04, 0.04],
        nwc_pct_of_rev_change=[0.10, 0.10, 0.08, 0.08, 0.08],
    )
    forecast = build_forecast(inputs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Default constants — used only when no explicit values are supplied.
# These are *not* hardcoded discount rates; they are operating-assumption
# starting points that the caller is expected to override.
# ---------------------------------------------------------------------------
_DEFAULT_PROJECTION_YEARS = 5


@dataclass
class ForecastInputs:
    """All inputs required to project 5 years of financials.

    Every list must contain exactly ``projection_years`` elements (default 5).
    Element [0] corresponds to Year 1, element [4] to Year 5.

    Attributes:
        base_revenue:              Year 0 (historical / LTM) revenue in absolute terms.
        revenue_growth_rates:      YoY revenue growth for each projected year.
        ebit_margins:              EBIT / Revenue target for each projected year.
        tax_rates:                 Effective tax rate applied to EBIT for each year.
        depreciation_pct_of_rev:   D&A as a % of revenue for each projected year.
        capex_pct_of_rev:          Capital expenditures as a % of revenue for each year.
        nwc_pct_of_rev_change:     Incremental NWC required per dollar of revenue
                                   growth (ΔWC = pct × ΔRevenue).  Captures the
                                   working-capital investment needed to support growth.
        projection_years:          Number of explicit forecast years (default 5).
    """

    base_revenue: float
    revenue_growth_rates: List[float]
    ebit_margins: List[float]
    tax_rates: List[float]
    depreciation_pct_of_rev: List[float]
    capex_pct_of_rev: List[float]
    nwc_pct_of_rev_change: List[float]
    projection_years: int = _DEFAULT_PROJECTION_YEARS

    def __post_init__(self) -> None:
        """Validate that all driver lists match the projection horizon."""
        n = self.projection_years
        drivers = {
            "revenue_growth_rates": self.revenue_growth_rates,
            "ebit_margins": self.ebit_margins,
            "tax_rates": self.tax_rates,
            "depreciation_pct_of_rev": self.depreciation_pct_of_rev,
            "capex_pct_of_rev": self.capex_pct_of_rev,
            "nwc_pct_of_rev_change": self.nwc_pct_of_rev_change,
        }
        for name, lst in drivers.items():
            if len(lst) != n:
                raise ValueError(
                    f"{name} has {len(lst)} elements but projection_years = {n}. "
                    f"Provide exactly {n} values."
                )
        if self.base_revenue <= 0:
            raise ValueError(
                f"base_revenue must be positive, got {self.base_revenue}"
            )


@dataclass
class ProjectedYear:
    """A single year of projected financial data.

    Attributes:
        year:           Projection year number (1-indexed).
        revenue:        Projected revenue.
        revenue_growth: YoY growth rate applied to reach this year's revenue.
        ebit:           Earnings Before Interest & Taxes.
        ebit_margin:    EBIT / Revenue.
        taxes:          Tax expense (applied to EBIT; floored at zero).
        nopat:          Net Operating Profit After Tax (EBIT − Taxes).
        depreciation:   Depreciation & Amortization.
        capex:          Capital Expenditures.
        change_in_nwc:  Change in Net Working Capital (positive = cash outflow).
        fcf:            Unlevered Free Cash Flow = NOPAT + D&A − CapEx − ΔWC.
    """

    year: int
    revenue: float
    revenue_growth: float
    ebit: float
    ebit_margin: float
    taxes: float
    nopat: float
    depreciation: float
    capex: float
    change_in_nwc: float
    fcf: float


@dataclass
class ForecastResult:
    """Complete forecast output.

    Attributes:
        inputs:       The ForecastInputs that produced this result.
        projections:  List of ProjectedYear, one per forecast year.
        terminal_fcf: The Year-N FCF used as the basis for terminal-value
                      estimation (equal to the last year's FCF).
    """

    inputs: ForecastInputs
    projections: List[ProjectedYear] = field(default_factory=list)
    terminal_fcf: float = 0.0


def build_forecast(inputs: ForecastInputs) -> ForecastResult:
    """Build a multi-year financial projection from the supplied assumptions.

    For each year *t* (1 … N):

        Revenue_t      = Revenue_{t-1} × (1 + growth_t)
        EBIT_t         = Revenue_t × ebit_margin_t
        Taxes_t        = max(0, EBIT_t × tax_rate_t)
        NOPAT_t        = EBIT_t − Taxes_t
        D&A_t          = Revenue_t × depreciation_pct_t
        CapEx_t        = Revenue_t × capex_pct_t
        ΔWC_t          = (Revenue_t − Revenue_{t-1}) × nwc_pct_t
        FCF_t          = NOPAT_t + D&A_t − CapEx_t − ΔWC_t

    Args:
        inputs: A fully-specified ForecastInputs dataclass.

    Returns:
        ForecastResult containing the year-by-year projections and the
        terminal-year FCF.
    """
    projections: List[ProjectedYear] = []
    prior_revenue = inputs.base_revenue

    for i in range(inputs.projection_years):
        year_num = i + 1
        growth = inputs.revenue_growth_rates[i]
        revenue = prior_revenue * (1.0 + growth)

        # --- Income statement ---
        ebit_margin = inputs.ebit_margins[i]
        ebit = revenue * ebit_margin

        tax_rate = inputs.tax_rates[i]
        taxes = max(0.0, ebit * tax_rate)
        nopat = ebit - taxes

        # --- Non-cash & reinvestment ---
        depreciation = revenue * inputs.depreciation_pct_of_rev[i]
        capex = revenue * inputs.capex_pct_of_rev[i]

        # Working-capital investment proportional to revenue growth
        delta_revenue = revenue - prior_revenue
        change_in_nwc = delta_revenue * inputs.nwc_pct_of_rev_change[i]

        # --- Free cash flow ---
        fcf = nopat + depreciation - capex - change_in_nwc

        projections.append(
            ProjectedYear(
                year=year_num,
                revenue=revenue,
                revenue_growth=growth,
                ebit=ebit,
                ebit_margin=ebit_margin,
                taxes=taxes,
                nopat=nopat,
                depreciation=depreciation,
                capex=capex,
                change_in_nwc=change_in_nwc,
                fcf=fcf,
            )
        )

        prior_revenue = revenue

    terminal_fcf = projections[-1].fcf if projections else 0.0

    return ForecastResult(
        inputs=inputs,
        projections=projections,
        terminal_fcf=terminal_fcf,
    )
