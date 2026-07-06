# utils/finance.py
"""
Financial data utilities — live market data via yfinance.

Fetches a company's current price, shares outstanding, historical revenue,
EBIT, and balance sheet data (cash, total debt) from Yahoo Finance, then
derives the assumptions needed to feed the DCF pipeline.

Usage:
    from utils.finance import fetch_ticker_data

    data = fetch_ticker_data("AAPL")
    print(f"Current price: ${data.current_price:,.2f}")
    print(f"Latest revenue: ${data.latest_revenue:,.0f}")
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import List, Optional

import yfinance as yf


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────


@dataclass
class TickerData:
    """Structured container for all data fetched from Yahoo Finance.

    Attributes:
        ticker:              Ticker symbol (uppercase).
        company_name:        Full company name.
        current_price:       Latest market price per share.
        shares_outstanding:  Fully diluted share count.
        beta:                Levered beta (systematic risk vs. market).
        market_cap:          Market capitalisation.
        total_debt:          Total long-term + short-term debt.
        total_cash:          Cash & cash equivalents + short-term investments.
        net_debt:            Total Debt − Total Cash.
        historical_revenue:  Annual revenues, most recent first (up to 4 years).
        historical_ebit:     Annual EBIT, most recent first (up to 4 years).
        revenue_growth_rates: YoY growth rates derived from historical revenue
                              (most recent first; len = len(historical_revenue) − 1).
        latest_revenue:      Most recent annual revenue.
        latest_ebit:         Most recent annual EBIT.
        latest_ebit_margin:  latest_ebit / latest_revenue.
    """

    ticker: str
    company_name: str
    current_price: float
    shares_outstanding: float
    beta: float
    market_cap: float
    total_debt: float
    total_cash: float
    net_debt: float
    historical_revenue: List[float] = field(default_factory=list)
    historical_ebit: List[float] = field(default_factory=list)
    revenue_growth_rates: List[float] = field(default_factory=list)
    latest_revenue: float = 0.0
    latest_ebit: float = 0.0
    latest_ebit_margin: float = 0.0


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _safe_get(info: dict, *keys, default=None):
    """Try multiple keys in order, returning the first non-None value."""
    for k in keys:
        val = info.get(k)
        if val is not None:
            return val
    return default


def _extract_row(df, *row_names) -> List[float]:
    """Extract a row from a yfinance DataFrame by trying multiple label names.

    yfinance column headers are dates (most recent first by default).
    Returns values as a list of floats, most-recent-year first.
    """
    if df is None or df.empty:
        return []
    for name in row_names:
        if name in df.index:
            row = df.loc[name]
            # Drop NaN and convert to float
            values = [float(v) for v in row.dropna().values]
            return values
    return []


def _compute_growth_rates(revenues: List[float]) -> List[float]:
    """Compute YoY growth rates from a list of revenues (most-recent-first).

    Returns growth rates most-recent-first. E.g. if revenues = [120, 100, 80],
    growth_rates = [0.20, 0.25] (120/100-1, 100/80-1).
    """
    rates = []
    for i in range(len(revenues) - 1):
        current = revenues[i]
        prior = revenues[i + 1]
        if prior > 0:
            rates.append(current / prior - 1.0)
        else:
            rates.append(0.0)
    return rates


# ──────────────────────────────────────────────────────────────────────
# Main fetch function
# ──────────────────────────────────────────────────────────────────────


def fetch_ticker_data(symbol: str) -> TickerData:
    """Fetch live financial data for a ticker from Yahoo Finance.

    Pulls:
      - Current price, shares outstanding, beta, market cap  (from .info)
      - Historical revenue and EBIT                          (from .financials)
      - Total debt and total cash                            (from .balance_sheet)

    Derives:
      - Net debt, historical growth rates, EBIT margin.

    Args:
        symbol: Ticker symbol (e.g. "AAPL", "MSFT").

    Returns:
        A populated TickerData dataclass.

    Raises:
        SystemExit: If critical data (price, revenue) cannot be retrieved.
    """
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}

    # ── Price & market data ──────────────────────────────────────────
    current_price = _safe_get(
        info,
        "currentPrice",
        "regularMarketPrice",
        "previousClose",
        default=0.0,
    )
    shares_outstanding = _safe_get(
        info,
        "sharesOutstanding",
        "impliedSharesOutstanding",
        default=0.0,
    )
    beta = _safe_get(info, "beta", default=1.0)
    market_cap = _safe_get(info, "marketCap", default=current_price * shares_outstanding)
    company_name = _safe_get(info, "longName", "shortName", default=symbol)

    if current_price <= 0:
        print(f"ERROR: Could not retrieve a valid price for '{symbol}'.")
        print("       Check the ticker symbol and your internet connection.")
        sys.exit(1)

    # ── Income statement (annual) ────────────────────────────────────
    financials = ticker.financials  # columns = dates, index = line items
    historical_revenue = _extract_row(
        financials,
        "Total Revenue",
        "Revenue",
        "Operating Revenue",
    )
    historical_ebit = _extract_row(
        financials,
        "EBIT",
        "Operating Income",
        "Net Income From Continuing Operation Net Minority Interest",
    )

    if not historical_revenue:
        print(f"ERROR: Could not retrieve revenue history for '{symbol}'.")
        sys.exit(1)

    latest_revenue = historical_revenue[0] if historical_revenue else 0.0
    latest_ebit = historical_ebit[0] if historical_ebit else 0.0
    latest_ebit_margin = latest_ebit / latest_revenue if latest_revenue > 0 else 0.0

    revenue_growth_rates = _compute_growth_rates(historical_revenue)

    # ── Balance sheet ────────────────────────────────────────────────
    balance_sheet = ticker.balance_sheet
    total_debt_vals = _extract_row(
        balance_sheet,
        "Total Debt",
        "Long Term Debt",
        "Long Term Debt And Capital Lease Obligation",
    )
    total_cash_vals = _extract_row(
        balance_sheet,
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "Cash",
    )

    total_debt = total_debt_vals[0] if total_debt_vals else 0.0
    total_cash = total_cash_vals[0] if total_cash_vals else 0.0
    net_debt = total_debt - total_cash

    return TickerData(
        ticker=symbol.upper(),
        company_name=company_name,
        current_price=current_price,
        shares_outstanding=shares_outstanding,
        beta=beta,
        market_cap=market_cap,
        total_debt=total_debt,
        total_cash=total_cash,
        net_debt=net_debt,
        historical_revenue=historical_revenue,
        historical_ebit=historical_ebit,
        revenue_growth_rates=revenue_growth_rates,
        latest_revenue=latest_revenue,
        latest_ebit=latest_ebit,
        latest_ebit_margin=latest_ebit_margin,
    )
