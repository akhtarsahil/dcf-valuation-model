# 🤫🧏 DCF Valuation Model: Valuemaxxing Stock Intrinsic Value

**Stop buying stocks based on P/E multiple copes. Time to valuemax your portfolio and check who is actually mogging the market.**

---

> *"Price is what you pay. Value is what you get."*
> — Warren Buffett (The ultimate 999-Stat Sigma GigaChad)

---

## 🚀 What is this?

This is a **Discounted Cash Flow (DCF) valuation engine** built in Python. If you are picking stocks based on stock-tok advice or P/E multiples, you are coping hard. Multiples assume peer companies aren't soyjaks. A DCF is the only way to actually check if a stock is an alpha value plays or if it's over.

This model projects 5 years of financials, checks if the cash flow rizz is real, adds the final boss (**Terminal Value**), and discounts everything to see who is under-valued and who is getting market-mogged.

---

## 🛠️ The Feature Build (Alpha Stats)

- **🔥 UFCF Cash Flow Rizz** — Projects EBIT margins and tax rates to see if the company actually makes real money or if they are just yapmaxxing.
- **💪 Dynamic WACC Mogging** — Computes dynamic cost of equity. Tells you if a company is a high-beta beta or a based, low-risk alpha.
- **📈 Terminal Growth perpetuity check** — Gordon Growth Model calculates if the stock's terminal value will mog the GDP in perpetuity.
- **🧠 Universal N-1 Solver [GIGACHAD Mode]** — Bypasses drivers. Leave any combination of variables (WACC, Growth, Terminal Value, or PV) blank, and click solve. The engine auto-detects what's missing and back-solves everything using Gordon Growth, PV discounting, and Brent's method root-finding.
- **🎨 Skibidi Streamlit Dashboard** — Web UI with real-time sliders, Plotly heatmaps for sensitivity matrices, and one-click PDF exports.
- **📊 2D WACC x TGR Heatmap** — Visually maps out exactly where the stock starts mogging the current market price.
- **🎭 Scenario preset shifts** — Toggle between **Bull** (Growth buffed, WACC debuffed), **Base** (Average run), and **Bear** (It's over, growth sliced, WACC spiked).

---

## 📥 Setup & run (No copes allowed)

### Prerequisites
- Python 3.10+
- `pip` package manager

### Getting started

```bash
# Clone the repository
git clone https://github.com/akhtarsahil/dcf-valuation-model.git
cd dcf-valuation-model

# Create a virtual environment (don't raw-dog your global packages)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

---

## 🕹️ How to check the stats (Usage)

### 1. Launch the Streamlit Dashboard (GUI Mode)
The ultimate playground. Manipulate sliders in real-time to watch the intrinsic price value-mog the market price.
```bash
streamlit run dashboard.py
```

Open `http://localhost:8501` in your browser. You will find two tabs:

#### 📈 Tab 1: Live Ticker DCF (The Standard Mog)
Use this tab to scrape live company financials from Yahoo Finance and run full-scale projected valuations.
* **Scrape Live Data**: Type any ticker (e.g., `AAPL`, `NVDA`, `MSFT`) in the sidebar search bar and hit Enter. The app scrapes the income statement, balance sheet, and beta in real-time.
* **Driver Customization**: Drag sliders to customize projected revenue growth rates, target EBIT margins, tax rates, and perpetual growth rates.
* **Scenario Preset Shifts**: Toggle between **Bull**, **Base**, and **Bear** modes. Watch the model shift all parameters dynamically based on preset macro-conditions.
* **Interactive Heatmaps**: Hover over the WACC x TGR sensitivity matrix. Locate the exact boundary where the stock changes from a "Buy" (value-mogging the price) to a "Sell" (over-valued cope).
* **Download PDF Report**: Click "Download PDF Report" in the sidebar to output a fully designed, tables-included corporate valuation report.

#### 🧠 Tab 2: Universal N-1 Solver (The Gigachad Auto-Solver)
Use this tab for textbook problems, exams, or quick back-of-the-envelope calculations where you bypass yfinance drivers entirely. No dropdowns, no disabled text boxes, and zero copes.
* **Clean Slate default**: Everything starts 100% blank when you open the solver. No default values to mess with your head.
* **Auto-format on blur**: Simply type raw numbers in the inputs. Type `100` in a USD box and move away—it instantly formats to `$100.00`. Type `14` in WACC or Terminal Growth Rate and move away—it formats to `14.00%`. Standard abbreviations like `1M` or `500K` are fully supported too.
* **Leave unknowns blank**: Leave whatever assumptions you don't know (such as **Terminal Value**, **Present Value (Target PV)**, **WACC (Discount Rate)**, or **Terminal Growth Rate ($g$)**) completely blank!
* **Run Valuation**: Click **🚀 Solve Valuation (Calculate All Blank Fields)** at the bottom of the page.
* **Auto-population**: The engine isolates the missing metrics, runs Brent's method root-finding or Gordon Growth formulas, and automatically populates the blank boxes with the computed results!
* **Feedback Banner**: A green success card lists exactly what values were solved on their own.

### 2. Run the CLI Mode
Query any ticker directly from Yahoo Finance and get a double-border ASCII terminal printout.
```bash
python app.py AAPL
python app.py TSLA
```

---

## 📐 Internal Math Mechanics (Real Sigma Science)

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE VALUEMAXXING PIPELINE                    │
│                                                                 │
│  yfinance (Scrapes the actuals)                                 │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────────┐     Decaying growth curves,                   │
│  │  Forecasting │◄─── margins mean-reverting (no yapmaxxing)    │
│  │    Engine     │                                               │
│  └──────┬───────┘                                               │
│         │ Projected operating schedules                         │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │   UFCF Build │  EBIT × (1 − t) + D&A − CapEx − ΔNWC          │
│  └──────┬───────┘                                               │
│         │ 5-year Cash Flow Rizz                                 │
│         ▼                                                       │
│  ┌──────────────┐     WACC (CAPM discount rate)                 │
│  │  Discounting │◄─── Terminal Growth Rate                      │
│  │   + Terminal  │                                               │
│  └──────┬───────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │  Valuation   │  Enterprise Value = PV(UFCF) + PV(Terminal)   │
│  │    Bridge    │  Equity Value = Enterprise Value − Net Debt   │
│  │              │  Share Price = Equity Value / Shares          │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Math formulas:

1. **Unlevered Free Cash Flow (UFCF)**:
   $$\text{UFCF} = \text{EBIT} \times (1 - \text{Tax Rate}) + \text{D&A} - \text{CapEx} - \Delta\text{Net Working Capital}$$
2. **Terminal Value (Gordon Growth)**:
   $$\text{Terminal Value} = \frac{\text{UFCF}_5 \times (1 + g)}{\text{WACC} - g}$$
3. **Discount Factor**:
   $$\text{PV} = \frac{\text{Cash Flow}}{(1 + \text{WACC})^t}$$
4. **N-1 Solver math (Gigachad inversion)**:
   - For **Perpetual Growth (g)**, we solve algebraically:
     $$g = \frac{\text{TV} \times \text{WACC} - \text{FCF}_N}{\text{TV} + \text{FCF}_N}$$
   - For **WACC (Discount Rate)**, we run `brentq` root-finding on the interval $[-0.99, 1.0]$ to solve for the rate where NPV equals the target NPV.

---

## 📂 Codebase structure

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

## ⚠️ Nerfs & Portfolio Risks (Major copes to watch for)

1. **Terminal Value Mogging**: About 70-85% of the calculated Enterprise Value comes from the Terminal Value. If you tweak WACC or TGR by a basis point, the valuation swings like crazy. Keep your assumptions grounded or it's over.
2. **Flat WACC Cope**: Assuming cost of capital never changes is a major cope. A real sigma company's risk profile evolves as it deleverages.
3. **SBC Fanum Tax**: Stock-Based Compensation is a real economic dilution. This model does not yet deduct the SBC Fanum Tax from the share price calculation.

---

## 🔮 Future DLC (Roadmap)

- [ ] **Monte Carlo Simulations** — Map out probability distributions on revenue growth and run 10,000 runs to see the probability of geting mogged.
- [ ] **Reverse DCF** — Feed in the current market price and solve for the implied growth rate the market is pricing in (solving the market cope).
- [ ] **Comparable Company Mogging (Trading Comps)** — Pull peer multiples and plot valuation football fields.

---

## 📜 License
Provided for educational and analytical purposes. Do not use this to raw-dog real-life investments. Do your own research!

*Built for analysts who believe spreadsheets belong in git, not attachments.*
