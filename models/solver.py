# models/solver.py
"""
Numerical solver for ManualDCFInputs.

Given a ManualDCFInputs dataclass with exactly one unknown field set to
None, this module algebraically or numerically solves for that variable
and returns a dictionary containing the variable name and its value.

Supported solve targets:
    - target_pv:          Discount cash_flows + terminal_value → PV.
    - initial_outlay_cf0: PV − target_npv → break-even initial outlay.
    - perpetual_growth:   Algebraic isolation of g from Gordon Growth.
    - wacc:               Brent's method root-finding for implied IRR.

Usage:
    from models.solver import solve_missing_variable

    result = solve_missing_variable(inputs)
    # result → {"variable": "wacc", "value": 0.0823}
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from scipy.optimize import brentq

from models.dcf import ManualDCFInputs


# ──────────────────────────────────────────────────────────────────────
# Internal discount-factor helpers
# ──────────────────────────────────────────────────────────────────────


def _discount_factor(
    rate: float,
    period: int,
    compounding_m: int,
    mid_year: bool,
) -> float:
    """Compute the present-value discount factor for a single period.

    Args:
        rate:           Nominal annual discount rate (as a decimal).
        period:         The period index (1-indexed).
        compounding_m:  Number of compounding sub-periods per period.
                        1 = annual, 2 = semi-annual, 12 = monthly.
        mid_year:       If True, discount to (period − 0.5) instead of
                        end-of-period to reflect average timing of receipts.

    Returns:
        Discount factor in (0, ∞).  For reasonable inputs this is in (0, 1].
    """
    t = (period - 0.5) if mid_year else float(period)

    if compounding_m == 1:
        # Simple annual compounding
        return 1.0 / ((1.0 + rate) ** t)
    else:
        # Sub-period compounding:  (1 + r/m)^(m·t)
        sub_rate = rate / compounding_m
        return 1.0 / ((1.0 + sub_rate) ** (compounding_m * t))


def _calculate_pv(
    rate: float,
    cash_flows: List[float],
    terminal_value: Optional[float],
    compounding_m: int,
    mid_year: bool,
) -> float:
    """Discount all future cash flows and the terminal value to present.

    The terminal value is always discounted at the END of the last period
    (not mid-year) because it represents a lump-sum value at the horizon.

    Args:
        rate:            Discount rate (decimal).
        cash_flows:      Period 1..N explicit cash flows.
        terminal_value:  Lump-sum terminal value at end of period N,
                         or None if not applicable.
        compounding_m:   Compounding frequency.
        mid_year:        Mid-year convention flag for the cash flows.

    Returns:
        Sum of discounted cash flows + discounted terminal value.
    """
    n = len(cash_flows)
    pv = 0.0

    # Discount each periodic cash flow
    for period, cf in enumerate(cash_flows, start=1):
        pv += cf * _discount_factor(rate, period, compounding_m, mid_year)

    # Discount terminal value at end-of-last-period (no mid-year shift)
    if terminal_value is not None and terminal_value != 0.0:
        pv += terminal_value * _discount_factor(rate, n, compounding_m, False)

    return pv


# ──────────────────────────────────────────────────────────────────────
# Public solver
# ──────────────────────────────────────────────────────────────────────


def solve_missing_variable(inputs: ManualDCFInputs) -> Dict[str, Union[str, float]]:
    """Solve for the single unknown variable in a ManualDCFInputs instance.

    The __post_init__ validator on ManualDCFInputs guarantees exactly one
    of (initial_outlay_cf0, target_pv, wacc, perpetual_growth) is None.
    This function dispatches to the appropriate algebraic or numerical
    solver and returns a dict with the variable name and computed value.

    Returns:
        {"variable": <field_name>, "value": <float>}

    Raises:
        ValueError: If the solver cannot converge or inputs are inconsistent.
    """

    # ── Case 1: Solve for target_pv ──────────────────────────────────
    #    Discount cash_flows + terminal_value at the given WACC.
    if inputs.target_pv is None:
        pv = _calculate_pv(
            rate=inputs.wacc,           # type: ignore[arg-type]
            cash_flows=inputs.cash_flows,
            terminal_value=inputs.terminal_value,
            compounding_m=inputs.compounding_m,
            mid_year=inputs.mid_year_convention,
        )
        return {"variable": "target_pv", "value": pv}

    # ── Case 2: Solve for initial_outlay_cf0 ─────────────────────────
    #    CF0 = target_npv − PV(future cash flows)
    #    i.e. the initial outlay that makes NPV equal the target.
    if inputs.initial_outlay_cf0 is None:
        pv = _calculate_pv(
            rate=inputs.wacc,           # type: ignore[arg-type]
            cash_flows=inputs.cash_flows,
            terminal_value=inputs.terminal_value,
            compounding_m=inputs.compounding_m,
            mid_year=inputs.mid_year_convention,
        )
        cf0 = inputs.target_npv - pv
        return {"variable": "initial_outlay_cf0", "value": cf0}

    # ── Case 3: Solve for perpetual_growth ───────────────────────────
    #    From Gordon Growth:  TV = FCF_N × (1 + g) / (WACC − g)
    #    Rearranging:
    #        TV × (WACC − g) = FCF_N × (1 + g)
    #        TV × WACC − TV × g = FCF_N + FCF_N × g
    #        TV × WACC − FCF_N = g × (TV + FCF_N)
    #        g = (TV × WACC − FCF_N) / (TV + FCF_N)
    if inputs.perpetual_growth is None:
        wacc = inputs.wacc                  # type: ignore[assignment]
        tv = inputs.terminal_value

        if tv is None or tv == 0.0:
            raise ValueError(
                "Cannot solve for perpetual_growth: terminal_value is "
                "None or zero.  A non-zero terminal value is required "
                "to back-solve the Gordon Growth rate."
            )

        # Use the last explicit cash flow as the terminal-year FCF
        fcf_n = inputs.cash_flows[-1]

        denominator = tv + fcf_n
        if denominator == 0.0:
            raise ValueError(
                "Cannot solve for perpetual_growth: (terminal_value + "
                "last cash flow) equals zero, causing division by zero."
            )

        g = (tv * wacc - fcf_n) / denominator

        # Sanity check: g must be less than WACC for convergence
        if g >= wacc:
            raise ValueError(
                f"Solved perpetual_growth ({g:.6f}) >= WACC ({wacc:.6f}).  "
                f"The Gordon Growth Model diverges when g >= WACC."
            )

        return {"variable": "perpetual_growth", "value": g}

    # ── Case 4: Solve for wacc (implied discount rate / IRR) ─────────
    #    Define: f(r) = CF0 + PV(cash_flows, r) + PV(TV, r) − target_npv
    #    Find r such that f(r) = 0 using Brent's bracketed root-finding.
    if inputs.wacc is None:
        cf0 = inputs.initial_outlay_cf0     # type: ignore[assignment]

        def _npv_objective(r: float) -> float:
            """NPV as a function of the discount rate r."""
            pv = _calculate_pv(
                rate=r,
                cash_flows=inputs.cash_flows,
                terminal_value=inputs.terminal_value,
                compounding_m=inputs.compounding_m,
                mid_year=inputs.mid_year_convention,
            )
            return cf0 + pv - inputs.target_npv

        # Bracketing interval: r ∈ (−0.99, 1.0)
        #   Lower bound −0.99 avoids division by zero at r = −1.
        #   Upper bound 1.0 (100% discount rate) covers extreme cases.
        try:
            implied_rate = brentq(
                _npv_objective,
                a=-0.99,
                b=1.0,
                xtol=1e-12,
                rtol=1e-12,
                maxiter=500,
            )
        except ValueError as exc:
            raise ValueError(
                f"Brent's method failed to converge on the interval "
                f"[-0.99, 1.0].  The NPV function may not cross zero "
                f"within this range.  Details: {exc}"
            ) from exc

        return {"variable": "wacc", "value": implied_rate}

    # This line should never be reached due to __post_init__ validation,
    # but serves as a safety net.
    raise ValueError("No solvable variable identified as None.")
