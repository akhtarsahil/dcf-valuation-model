# 🎮 DCF Valuation Model: Min-Maxing Stock Intrinsic Value

**Get good at finance. Stop guessing. Run the numbers like a speedrunner optimizer.**

---

> *"Price is what you pay. Value is what you get."*
> — Warren Buffett (The ultimate value-investing raid boss)

---

## 🚀 What is this?

This is a **Discounted Cash Flow (DCF) valuation engine** built in Python. If you've been picking stocks based on vibes or simple P/E multiples, you're playing on Easy mode with a default build. A DCF is how institutional analysts min-max their portfolio stats.

Given a company's raw inputs (revenue growth, operating margins, capital structure, and risk levels), this model projects its **Unlevered Free Cash Flows (UFCF)**, handles the final boss (**Terminal Value**), and discounts those cash flows back to present value. 

The goal? Figure out the company's **Implied Share Price** and see if it's currently on discount in the market or if it's overhyped.

---

## 🛠️ The Feature Set (Passive & Active Skills)

- **📈 5-Year Operating Forecast Engine** — Projects Revenue, EBIT margin, Tax rate, Depreciation, CapEx, and Working Capital.
- **⚡ Dynamic WACC (CAPM) Calculator** — Cost of Equity calculated dynamically using the risk-free rate, beta, and equity risk premium. No hardcoded discount rates.
- **👾 Gordon Growth Terminal Value Bridge** — Solves the perpetuity cash flow math beyond the explicit forecast period.
- **🎯 Manual N-1 Variable Solver [NEW]** — Input custom cash flows and structure. Solve for any missing stat: target PV, break-even initial outlay (CF₀), discount rate (WACC), or perpetual growth (g) using numerical optimization (`scipy.optimize.brentq`).
- **🎛️ Interactive Streamlit Dashboard** — Web GUI with real-time sliders, Plotly heatmaps for sensitivity matrices, and one-click PDF downloads.
- **📊 2D WACC x TGR Sensitivity Heatmaps** — Visualizes how changes in WACC and Terminal Growth swing the final valuation.
- **🎭 Scenario Stress-Testing** — Instant preset shifts for **Bull** (Buffed growth/margins, lower WACC), **Base** (Actual trend), and **Bear** (Debuffed growth/margins, higher WACC).
- **🖥️ Clean CLI Output** — Formatted terminal report with double-border Unicode tables.

---

## 📥 Setup & Installation (Getting Your Gear)

### Prerequisites
- Python 3.10+
- `pip` package manager

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/akhtarsahil/dcf-valuation-model.git
cd dcf-valuation-model

# Create a virtual environment to isolate dependencies
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install the required packages
pip install -r requirements.txt
```

---

## 🕹️ How to Play (Usage)

### 1. Launch the Streamlit Dashboard (GUI Mode)
The interactive hub. Perfect for real-time slider manipulation and visual heatmaps.
```bash
streamlit run dashboard.py
```

### 2. Run the Command-Line Interface (CLI Mode)
Pass a Yahoo Finance ticker to fetch live financials and generate an instant terminal report.
```bash
python app.py AAPL
python app.py MSFT
```

---

## 📐 How the Code works (Under the Hood)

```
┌─────────────────────────────────────────────────────────────────┐
│                        DCF DATA PIPELINE                        │
│                                                                 │
│  yfinance (Live Scraping)                                       │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────────┐     Decaying revenue growth,                  │
│  │  Forecasting │◄─── mean-reverting margins                    │
│  │    Engine     │                                               │
│  └──────┬───────┘                                               │
│         │ Projected operating schedules                         │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │   UFCF Build │  EBIT × (1 − t) + D&A − CapEx − ΔNWC          │
│  └──────┬───────┘                                               │
│         │ 5-year Free Cash Flows                                │
│         ▼                                                       │
│  ┌──────────────┐     WACC (from CAPM + Debt weight)            │
│  │  Discounting │◄─── Terminal Growth Rate                      │
│  │   + Terminal  │                                               │
│  └──────┬───────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │  Valuation   │  Enterprise Value = PV(FCFs) + PV(Terminal)   │
│  │    Bridge    │  Equity Value = Enterprise Value − Net Debt   │
│  │              │  Share Price = Equity Value / Shares          │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

### The Math Mechanics

1. **Unlevered Free Cash Flow (UFCF)**:
   $$\text{UFCF} = \text{EBIT} \times (1 - \text{Tax Rate}) + \text{D&A} - \text{CapEx} - \Delta\text{Net Working Capital}$$
2. **Terminal Value (Gordon Growth)**:
   $$\text{Terminal Value} = \frac{\text{UFCF}_5 \times (1 + g)}{\text{WACC} - g}$$
3. **Discount Factor**:
   $$\text{PV} = \frac{\text{Cash Flow}}{(1 + \text{WACC})^t}$$
4. **N-1 Solver Inversions**:
   - For **Perpetual Growth (g)**, we solve algebraically:
     $$g = \frac{\text{TV} \times \text{WACC} - \text{FCF}_N}{\text{TV} + \text{FCF}_N}$$
   - For **WACC (Discount Rate)**, we run `brentq` root-finding on the interval $[-0.99, 1.0]$ to solve for the rate where NPV equals the target NPV.

---

## 📂 File Structure

```
dcf-valuation-model/
├── app.py                  # CLI Entrypoint (Double-border terminal report)
├── dashboard.py            # Streamlit interactive web GUI
├── requirements.txt        # Package dependencies
├── .gitignore              # Ignores venv, pycache, and generated PDFs
│
├── models/
│   ├── dcf.py              # DCFInputs & ManualDCFInputs schemas
│   ├── forecasting.py      # Projects operating lines & FCFs
│   ├── wacc.py             # Computes WACC dynamically using CAPM
│   ├── valuation.py        # Scenario logic & WACC x TGR matrix
│   └── solver.py           # Numerical root-finding and algebraic solvers
│
└── utils/
    ├── finance.py          # yfinance API scraper & robust fallback parser
    └── helpers.py          # ReportLab PDF design layouts & tables
```

---

## ⚠️ Nerfs & Limitations (Read before raiding)

1. **Terminal Value Dominance**: About 70-85% of the calculated Enterprise Value comes from the Terminal Value. If you tweak WACC or Perpetual Growth by even a fraction of a percent, your output price will swing wildly. Always check the **Sensitivity Heatmap** to see how volatile your valuation is.
2. **Flat WACC**: The model assumes risk remains constant forever. In the real world, a company's WACC decreases as it matures.
3. **No SBC Adjustments**: Stock-Based Compensation is a real cash-like dilution to common shareholders. This model does not yet deduct expected SBC dilution.

---

## 🔮 Future DLC (Roadmap)

- [ ] **Monte Carlo Simulations** — Configure probability distributions on revenue growth and run 10,000 runs to get a probability distribution of the share price.
- [ ] **Reverse DCF** — Feed in the current market price and solve for the implied revenue growth rate the market is pricing in.
- [ ] **Multi-stage Growth** — Define distinct growth phases (e.g. 5 years of hypergrowth, 5 years of transition, then steady state).
- [ ] **EDGAR Financial Scraper** — Automatically parse 10-K and 10-Q filings directly from the SEC SEC EDGAR API.

---

## 📜 License
Provided for educational and analytical purposes. Do not use this as your sole source of investment decisions. Do your own research!

*Built for analysts who believe spreadsheets belong in git, not attachments.*
