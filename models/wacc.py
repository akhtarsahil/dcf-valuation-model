# models/wacc.py
"""
Weighted Average Cost of Capital (WACC) calculator.

Computes the blended discount rate dynamically from user-supplied inputs.
No hardcoded rates — every parameter must be explicitly provided.

Components:
  - Cost of Equity  (via CAPM: Rf + β × ERP)
  - Cost of Debt    (pre-tax yield × (1 − tax rate))
  - Capital structure weights (debt ratio + equity ratio must sum to 1.0)

Usage:
    from models.wacc import WACCInputs, calculate_wacc

    inputs = WACCInputs(
        risk_free_rate=0.043,
        beta=1.15,
        equity_risk_premium=0.055,
        cost_of_debt_pretax=0.05,
        tax_rate=0.21,
        debt_ratio=0.30,
        equity_ratio=0.70,
    )
    wacc = calculate_wacc(inputs)
"""

from dataclasses import dataclass


@dataclass
class WACCInputs:
    """All inputs required to compute WACC dynamically.

    Attributes:
        risk_free_rate:        Yield on the benchmark government bond (e.g. 10-yr Treasury).
        beta:                  Levered beta of the equity — measures systematic risk relative
                               to the market.
        equity_risk_premium:   Expected excess return of the broad equity market over the
                               risk-free rate (ERP / Market Premium).
        cost_of_debt_pretax:   Weighted-average pre-tax yield on the company's outstanding debt.
        tax_rate:              Marginal corporate tax rate used to compute the after-tax
                               cost of debt (interest tax shield).
        debt_ratio:            Market-value weight of debt in the capital structure (D / V).
        equity_ratio:          Market-value weight of equity in the capital structure (E / V).
                               debt_ratio + equity_ratio must equal 1.0.
    """

    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    cost_of_debt_pretax: float
    tax_rate: float
    debt_ratio: float
    equity_ratio: float

    def __post_init__(self) -> None:
        """Validate inputs on construction."""
        weight_sum = round(self.debt_ratio + self.equity_ratio, 10)
        if weight_sum != 1.0:
            raise ValueError(
                f"debt_ratio ({self.debt_ratio}) + equity_ratio ({self.equity_ratio}) "
                f"= {weight_sum}, but must equal 1.0"
            )
        if self.beta < 0:
            raise ValueError(f"beta must be non-negative, got {self.beta}")
        if not (0.0 <= self.tax_rate < 1.0):
            raise ValueError(f"tax_rate must be in [0, 1), got {self.tax_rate}")
        if self.debt_ratio < 0 or self.equity_ratio < 0:
            raise ValueError("Capital-structure weights must be non-negative")


@dataclass
class WACCResult:
    """Detailed WACC computation result.

    Stores every intermediate value so downstream consumers (reports,
    sensitivity tables, debug logs) can inspect the full breakdown.

    Attributes:
        cost_of_equity:        CAPM cost of equity (Rf + β × ERP).
        cost_of_debt_pretax:   Pre-tax cost of debt (pass-through from inputs).
        cost_of_debt_aftertax: After-tax cost of debt (Kd × (1 − t)).
        debt_ratio:            D / V weight.
        equity_ratio:          E / V weight.
        wacc:                  Blended weighted average cost of capital.
    """

    cost_of_equity: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    debt_ratio: float
    equity_ratio: float
    wacc: float


def calculate_cost_of_equity(
    risk_free_rate: float,
    beta: float,
    equity_risk_premium: float,
) -> float:
    """Capital Asset Pricing Model (CAPM).

    Ke = Rf + β × ERP

    Args:
        risk_free_rate:       Benchmark risk-free rate.
        beta:                 Levered equity beta.
        equity_risk_premium:  Broad market excess return over Rf.

    Returns:
        Cost of equity as a decimal (e.g. 0.1065 for 10.65%).
    """
    return risk_free_rate + beta * equity_risk_premium


def calculate_cost_of_debt_aftertax(
    cost_of_debt_pretax: float,
    tax_rate: float,
) -> float:
    """After-tax cost of debt.

    Kd_at = Kd × (1 − t)

    The tax shield on interest expense reduces the effective cost of debt
    financing to the firm.

    Args:
        cost_of_debt_pretax: Weighted-average pre-tax yield on debt.
        tax_rate:            Marginal corporate tax rate.

    Returns:
        After-tax cost of debt as a decimal.
    """
    return cost_of_debt_pretax * (1.0 - tax_rate)


def calculate_wacc(inputs: WACCInputs) -> WACCResult:
    """Compute WACC from first principles — no hardcoded values.

    WACC = (E/V) × Ke  +  (D/V) × Kd × (1 − t)

    This is the discount rate used to convert future unlevered free cash
    flows into present value.  It reflects the blended required return
    demanded by all capital providers (equity holders and debt holders),
    weighted by their respective shares of the firm's total capital.

    Args:
        inputs: A fully-specified WACCInputs dataclass.

    Returns:
        WACCResult with the computed WACC and all intermediate values.
    """
    ke = calculate_cost_of_equity(
        inputs.risk_free_rate,
        inputs.beta,
        inputs.equity_risk_premium,
    )

    kd_at = calculate_cost_of_debt_aftertax(
        inputs.cost_of_debt_pretax,
        inputs.tax_rate,
    )

    wacc = (inputs.equity_ratio * ke) + (inputs.debt_ratio * kd_at)

    return WACCResult(
        cost_of_equity=ke,
        cost_of_debt_pretax=inputs.cost_of_debt_pretax,
        cost_of_debt_aftertax=kd_at,
        debt_ratio=inputs.debt_ratio,
        equity_ratio=inputs.equity_ratio,
        wacc=wacc,
    )
