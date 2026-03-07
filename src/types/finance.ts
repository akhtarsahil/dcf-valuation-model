export interface Assumptions {
  year0Revenue: number;
  revenueGrowthRates: number[]; // 5 years, e.g., [0.15, 0.12, 0.10, 0.08, 0.05]
  grossMargin: number; // e.g., 0.75
  sgaPercentOfRev: number; // e.g., 0.40
  taxRate: number; // e.g., 0.21
  dso: number; // Days Sales Outstanding
  dio: number; // Days Inventory Outstanding
  dpo: number; // Days Payable Outstanding
  capexPercentOfRev: number; // e.g., 0.05
  daPercentOfCapex: number; // D&A as % of CapEx, e.g., 1.0 (approx to keep PPE flat)
  wacc: number; // Discount rate, e.g., 0.10
  terminalGrowthRate: number; // e.g., 0.02
  sharesOutstanding: number; // e.g., 1000
  netDebt: number; // Total Debt - Cash
}

export interface FinancialYear {
  year: number; // 0 to 5
  
  // Income Statement
  revenue: number;
  yoyGrowth: number;
  cogs: number;
  grossProfit: number;
  grossMargin: number; // percentage
  sga: number;
  ebitda: number;
  ebitdaMargin: number; // percentage
  depreciation: number;
  ebit: number;
  taxes: number;
  netIncome: number;
  netIncomeMargin: number; // percentage

  // Balance Sheet (Key Working Capital items)
  accountsReceivable: number;
  inventory: number;
  accountsPayable: number;
  netWorkingCapital: number;
  changeInNwc: number; // Current NWC - Prior NWC
  
  // Cash Flow
  capex: number;
  unleveredFreeCashFlow: number;

  // DCF Math
  discountFactor: number;
  presentValueUFCF: number;
}

export interface ValuationOutput {
  wacc: number;
  terminalYearUFCF: number;
  terminalValue: number;
  pvOfTerminalValue: number;
  npvOfUFCF: number; // Sum of PV of UFCF years 1-5
  enterpriseValue: number;
  netDebt: number;
  equityValue: number;
  sharesOutstanding: number;
  impliedSharePrice: number;
}

export interface ModelOutput {
  assumptions: Assumptions;
  projections: FinancialYear[];
  valuation: ValuationOutput;
}
