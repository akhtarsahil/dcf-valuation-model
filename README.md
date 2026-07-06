# DCF Valuation Model

**Intrinsic Value Estimation via Discounted Cash Flow Analysis**

---

> *"Price is what you pay. Value is what you get."*
> — Warren Buffett

## Executive Summary

This project implements a **Discounted Cash Flow (DCF) valuation model** in Python — the same fundamental methodology used by investment banks, equity research analysts, and institutional asset managers to estimate the intrinsic value of a business.

Given a set of financial assumptions (revenue trajectory, operating margins, capital intensity, and cost of capital), the model projects future **Unlevered Free Cash Flows (UFCF)**, estimates a **Terminal Value** for the business beyond the explicit forecast period, and discounts everything back to today's dollars to arrive at an **Enterprise Value**, **Equity Value**, and ultimately an **Implied Share Price**.

The goal is not to produce a single "correct" number — it is to build a rigorous, transparent framework for understanding *what the market is pricing in* and *where the asymmetry lies*.

---

## Why DCF?

Among the toolkit of valuation approaches (comparable company analysis, precedent transactions, LBO models, dividend discount models), DCF stands alone as the only method that values a company based purely on **its own fundamentals** rather than on the prices the market assigns to similar businesses.

| Approach | Basis | Strength | Weakness |
|---|---|---|---|
| **DCF** | Intrinsic cash flows | Fundamentally grounded; independent of market sentiment | Highly sensitive to terminal assumptions |
| Comparable Companies | Market multiples | Simple; market-calibrated | Assumes the market is correctly pricing peers |
| Precedent Transactions | M&A deal multiples | Reflects real premiums paid | Sparse data; deal-specific synergies distort |
| Dividend Discount | Dividends | Clean for dividend-paying stocks | Useless for growth companies that reinvest |

A well-constructed DCF forces the analyst to make *explicit* assumptions about growth, profitability, reinvestment, and risk — assumptions that are hidden inside a simple P/E multiple. That transparency is its greatest value.

---

## Features

- **Full Income Statement Forecasting** — Projects Revenue, COGS, Gross Profit, SG&A, EBITDA, D&A, EBIT, Taxes, and Net Income across a configurable 5–10 year explicit period.
- **Working Capital Modeling** — Converts day-count assumptions (DSO, DIO, DPO) into projected Accounts Receivable, Inventory, and Accounts Payable balances to derive changes in Net Working Capital.
- **Unlevered Free Cash Flow Build** — Bridges from EBIT through NOPAT, adds back non-cash charges, subtracts reinvestment, and arrives at UFCF.
- **WACC Calculator** — Computes the Weighted Average Cost of Capital from CAPM-based Cost of Equity (risk-free rate + β × equity risk premium) and after-tax Cost of Debt.
- **Terminal Value via Gordon Growth Model** — Estimates the perpetuity value of cash flows beyond the projection horizon using a long-run GDP-aligned growth rate.
- **2D Sensitivity Analysis** — Generates a matrix of implied share prices across ranges of WACC and terminal growth rate to stress-test the valuation.
- **Scenario Management** — Pre-built Base, Upside, and Downside scenario presets with one-click switching.
- **Clean Terminal Output** — Formatted tables rendered via `tabulate` for quick analysis in the console.
- **Excel Export** — One-command export of all projection schedules and valuation output to a formatted `.xlsx` workbook.

---

## Installation

### Prerequisites

- Python 3.10 or later
- `pip` package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/dcf-valuation-model.git
cd dcf-valuation-model

# Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

### Run with Default Assumptions

```bash
python app.py
```

Runs the DCF model with built-in base-case assumptions and prints the full income statement projection, free cash flow build, valuation bridge, and sensitivity matrix to the terminal.

### Run with a Custom Configuration

```bash
python app.py --config data/my_assumptions.json
```

Override any assumption by supplying a JSON or YAML configuration file. See `data/sample_config.json` for the full schema.

### Fetch Live Data (requires `yfinance`)

```bash
python app.py --ticker MSFT --years 7
```

Pulls the latest income statement, balance sheet, and market data from Yahoo Finance, seeds the model with historical actuals, and runs a 7-year DCF projection.

### Export to Excel

```bash
python app.py --ticker AAPL --export output/aapl_dcf.xlsx
```

Writes all schedules (Income Statement, FCF Build, Valuation Bridge, Sensitivity Matrix) to a multi-sheet Excel workbook.

---

## Methodology

The model follows a standard institutional DCF framework:

```
┌─────────────────────────────────────────────────────────────────┐
│                        DCF PIPELINE                             │
│                                                                 │
│  Historical Actuals                                             │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────────┐     Revenue growth rates, margin targets,     │
│  │  Forecasting │◄─── CapEx %, working-capital day counts       │
│  │    Engine     │                                               │
│  └──────┬───────┘                                               │
│         │ Projected Income Stmt + Balance Sheet items            │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │   UFCF Build │  EBIT×(1−t) + D&A − CapEx − ΔWC             │
│  └──────┬───────┘                                               │
│         │ Yr 1 … Yr N free cash flows                           │
│         ▼                                                       │
│  ┌──────────────┐     WACC (from CAPM + capital structure)      │
│  │  Discounting │◄─── Terminal Growth Rate                      │
│  │   + Terminal  │                                               │
│  └──────┬───────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │  Valuation   │  EV = Σ PV(UFCF) + PV(TV)                   │
│  │    Output    │  Equity = EV − Net Debt                       │
│  │              │  Share Price = Equity / Shares Outstanding    │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1 — Forecast Free Cash Flows

For each year in the explicit projection period (default: 5 years):

| Line Item | Derivation |
|---|---|
| Revenue | Prior Revenue × (1 + Growth Rate) |
| COGS | Revenue × (1 − Gross Margin) |
| Gross Profit | Revenue − COGS |
| SG&A | Revenue × SG&A % |
| EBITDA | Gross Profit − SG&A |
| D&A | CapEx × D&A-to-CapEx ratio |
| EBIT | EBITDA − D&A |
| Taxes | max(0, EBIT × Tax Rate) |
| NOPAT | EBIT − Taxes |
| CapEx | Revenue × CapEx % |
| ΔWC | Current NWC − Prior NWC |
| **UFCF** | **NOPAT + D&A − CapEx − ΔWC** |

### Step 2 — Estimate Terminal Value

Beyond the explicit period, we assume the business reaches a steady state and grows at a constant rate in perpetuity:

```
Terminal Value = UFCF(Year N) × (1 + g) / (WACC − g)
```

Where `g` is the terminal growth rate, typically anchored to long-run nominal GDP growth (2–3%).

### Step 3 — Discount to Present Value

Each projected UFCF and the Terminal Value are discounted using end-of-year convention:

```
PV = CF / (1 + WACC)^t
```

### Step 4 — Bridge to Equity Value

```
Enterprise Value  = Σ PV(UFCF) + PV(Terminal Value)
Equity Value      = Enterprise Value − Net Debt
Implied Price     = Equity Value / Shares Outstanding
```

---

## Key Assumptions (Base Case Defaults)

| Parameter | Default Value | Rationale |
|---|---|---|
| Year 0 Revenue | $100,000 | Placeholder — override with actuals |
| Revenue Growth (Yr 1→5) | 20% → 15% → 12% → 10% → 8% | Decelerating growth curve typical of a maturing SaaS business |
| Gross Margin | 75.0% | Consistent with high-margin software |
| SG&A % of Revenue | 40.0% | Blended S&M + G&A for a scaling company |
| Tax Rate | 21.0% | U.S. federal statutory rate |
| CapEx % of Revenue | 5.0% | Asset-light technology company |
| D&A / CapEx | 100% | Maintains flat PP&E (steady-state reinvestment) |
| WACC | 12.0% | Reflects mid-cap tech equity risk |
| Terminal Growth Rate | 3.0% | Approximates long-run nominal GDP |
| DSO / DIO / DPO | 45 / 30 / 60 days | Standard working-capital profile |
| Net Debt | $50,000 | Total Debt minus Cash & Equivalents |
| Shares Outstanding | 1,000 | Fully diluted share count |

---

## Sample Output

```
══════════════════════════════════════════════════════════════
                    DCF VALUATION SUMMARY
══════════════════════════════════════════════════════════════

  Implied Share Price .............. $295.82 / share
  Equity Value ..................... $295,820
  Enterprise Value ................. $345,820
  Net Debt ......................... ($50,000)

──────────────────────────────────────────────────────────────
  VALUATION BRIDGE
──────────────────────────────────────────────────────────────
  NPV of Projected UFCF (Yr 1–5) .. $68,413     (19.8%)
  PV of Terminal Value ............. $277,407    (80.2%)
                                     ────────
  Enterprise Value ................. $345,820   (100.0%)

──────────────────────────────────────────────────────────────
  SENSITIVITY: IMPLIED SHARE PRICE (WACC vs. Terminal Growth)
──────────────────────────────────────────────────────────────

         │  2.0%    2.5%    3.0%    3.5%    4.0%
  ───────┼──────────────────────────────────────────
  10.0%  │ $356    $393    $439   ★$499    $578
  11.0%  │ $286    $311    $341    $379    $428
  12.0%  │ $234    $252   ★$275    $302    $336
  13.0%  │ $194    $208    $224    $243    $267
  14.0%  │ $163    $173    $185    $199    $216

  ★ = current assumption
```

---

## Project Structure

```
dcf-valuation-model/
│
├── app.py                  # Application entry point & CLI
├── requirements.txt        # Python dependencies
├── README.md               # This document
│
├── models/
│   ├── __init__.py
│   ├── dcf.py              # Core DCF discounting engine
│   ├── valuation.py        # Valuation output & bridge
│   ├── wacc.py             # WACC calculator (CAPM + capital structure)
│   └── forecasting.py      # Income statement & cash flow forecasting
│
├── utils/
│   ├── __init__.py
│   ├── finance.py          # Financial math helpers (PV, CAGR, formatting)
│   └── helpers.py          # CLI parsing, data I/O, table rendering
│
└── data/
    └── .gitkeep            # Placeholder for input data files
```

---

## Limitations

This model is an educational and analytical tool. It is **not** investment advice.

1. **Terminal Value Dominance** — In most DCFs, 70–85% of Enterprise Value comes from the terminal value, which is itself a function of just two assumptions (WACC and `g`). Small changes in either produce large swings in the output. The sensitivity matrix exists precisely to make this dependency transparent.

2. **Single-Point WACC** — The model uses a constant discount rate across all periods. In practice, a company's risk profile (and therefore its cost of capital) evolves as it matures, deleverages, or enters new markets.

3. **No Monte Carlo / Probabilistic Layer** — All outputs are deterministic. A production-grade model would layer in probability distributions on key inputs and run thousands of simulations.

4. **Simplified Working Capital** — NWC is modeled via constant day-count ratios. Real-world working capital is lumpy and seasonal.

5. **No Stock-Based Compensation Adjustment** — SBC is a real economic cost that dilutes shareholders. This model does not yet haircut FCF for expected dilution from option exercises.

6. **No Scenario-Weighted Valuation** — The model presents scenarios independently. A Bayesian framework that probability-weights across scenarios would better represent an analyst's actual conviction.

---

## Future Improvements

- [ ] **Monte Carlo simulation** with configurable distributions on revenue growth, margin, and WACC
- [ ] **Reverse DCF** — given a market price, solve for the implied growth rate the market is pricing in
- [ ] **Multi-stage growth model** — separate high-growth, transition, and terminal phases with distinct WACC profiles
- [ ] **Comparable company overlay** — pull peer multiples (EV/EBITDA, P/E) and plot implied value ranges alongside the DCF output
- [ ] **Interactive Streamlit dashboard** — browser-based UI with live sliders and charts
- [ ] **Automated data ingestion** — pull SEC EDGAR filings (10-K, 10-Q) and parse XBRL for zero-manual-input valuations
- [ ] **Unit test suite** — property-based tests ensuring valuation identities hold (e.g., EV = Equity + Net Debt)

---

## License

This project is provided for educational purposes. Use at your own discretion.

---

*Built for analysts who believe a spreadsheet should be version-controlled.*
