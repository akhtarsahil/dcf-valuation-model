import { Assumptions, FinancialYear, ModelOutput, ValuationOutput } from '../types/finance';

export function runDCFModel(assumptions: Assumptions): ModelOutput {
  const projections: FinancialYear[] = [];
  
  // Array of 6 years (0 to 5)
  for (let y = 0; y <= 5; y++) {
    const isYear0 = y === 0;
    const priorYear = isYear0 ? null : projections[y - 1];

    // --- Income Statement ---
    let revenue = 0;
    let yoyGrowth = 0;

    if (isYear0) {
      revenue = assumptions.year0Revenue;
    } else {
      yoyGrowth = assumptions.revenueGrowthRates[y - 1];
      revenue = priorYear!.revenue * (1 + yoyGrowth);
    }

    const grossProfit = revenue * assumptions.grossMargin;
    const cogs = revenue - grossProfit;
    const sga = revenue * assumptions.sgaPercentOfRev;
    const ebitda = grossProfit - sga;
    const ebitdaMargin = revenue > 0 ? ebitda / revenue : 0;

    const capex = revenue * assumptions.capexPercentOfRev;
    const depreciation = capex * assumptions.daPercentOfCapex;
    const ebit = ebitda - depreciation;

    // Simplified taxes: Tax rate applied to EBIT
    const taxes = Math.max(0, ebit * assumptions.taxRate); 
    const netIncome = ebit - taxes;
    const netIncomeMargin = revenue > 0 ? netIncome / revenue : 0;

    // --- Balance Sheet (Working Capital) ---
    // Accounts Receivable = (Revenue / 365) * DSO
    const accountsReceivable = (revenue / 365) * assumptions.dso;
    
    // Inventory = (COGS / 365) * DIO
    const inventory = (cogs / 365) * assumptions.dio;
    
    // Accounts Payable = (COGS / 365) * DPO
    const accountsPayable = (cogs / 365) * assumptions.dpo;
    
    const netWorkingCapital = accountsReceivable + inventory - accountsPayable;
    
    const changeInNwc = isYear0 ? 0 : netWorkingCapital - priorYear!.netWorkingCapital;

    // --- Cash Flow ---
    // Unlevered Free Cash Flow (UFCF) = EBIT*(1-t) + D&A - CapEx - Change in NWC
    // Notice EBIT*(1-t) is just ebit - taxes in our simple model
    const unleveredFreeCashFlow = isYear0 ? 0 : ebit - taxes + depreciation - capex - changeInNwc;

    // --- DCF Math ---
    // Discount factor = 1 / (1 + WACC)^t
    // We only discount future cash flows (years 1-5)
    let discountFactor = 0;
    let presentValueUFCF = 0;
    if (!isYear0) {
       // Mid-year convention could be used, but standard end-of-year is simpler
       discountFactor = 1 / Math.pow(1 + assumptions.wacc, y);
       presentValueUFCF = unleveredFreeCashFlow * discountFactor;
    }

    projections.push({
      year: y,
      revenue,
      yoyGrowth,
      cogs,
      grossProfit,
      grossMargin: assumptions.grossMargin,
      sga,
      ebitda,
      ebitdaMargin,
      depreciation,
      ebit,
      taxes,
      netIncome,
      netIncomeMargin,
      
      accountsReceivable,
      inventory,
      accountsPayable,
      netWorkingCapital,
      changeInNwc,
      
      capex,
      unleveredFreeCashFlow,
      
      discountFactor,
      presentValueUFCF
    });
  }

  // --- Terminal Value & Target Valuation ---
  const year5 = projections[5];
  
  // Terminal Year UFCF = Year 5 UFCF * (1 + Terminal Growth Rate)
  const terminalYearUFCF = year5.unleveredFreeCashFlow * (1 + assumptions.terminalGrowthRate);
  
  // Gordon Growth Model: TV = Terminal Year UFCF / (WACC - Terminal Growth Rate)
  const terminalValue = terminalYearUFCF / (assumptions.wacc - assumptions.terminalGrowthRate);
  const pvOfTerminalValue = terminalValue * year5.discountFactor;

  // Sum PV of UFCF for Years 1-5
  const npvOfUFCF = projections.reduce((sum, curr) => sum + curr.presentValueUFCF, 0);
  
  // Enterprise Value = NPV of UFCF + PV of Terminal Value
  const enterpriseValue = npvOfUFCF + pvOfTerminalValue;
  
  // Equity Value = Enterprise Value - Net Debt
  const equityValue = enterpriseValue - assumptions.netDebt;
  
  // Share Price
  const impliedSharePrice = equityValue / assumptions.sharesOutstanding;

  const valuation: ValuationOutput = {
    wacc: assumptions.wacc,
    terminalYearUFCF,
    terminalValue,
    pvOfTerminalValue,
    npvOfUFCF,
    enterpriseValue,
    netDebt: assumptions.netDebt,
    equityValue,
    sharesOutstanding: assumptions.sharesOutstanding,
     impliedSharePrice: isNaN(impliedSharePrice) ? 0 : Math.max(0, impliedSharePrice)
  };

  return {
    assumptions,
    projections,
    valuation
  };
}
