'use client';

import React, { useState, useMemo } from 'react';
import { Assumptions } from '../types/finance';
import { runDCFModel } from '../lib/financeEngine';
import { AssumptionSlider } from '../components/AssumptionSlider';
import { AssumptionInput } from '../components/AssumptionInput';
import { FinancialTable } from '../components/FinancialTable';
import { ValuationDashboard } from '../components/ValuationDashboard';
import { ScenarioManager } from '../components/ScenarioManager';
import { SensitivityMatrix } from '../components/SensitivityMatrix';

const DEFAULT_ASSUMPTIONS: Assumptions = {
  year0Revenue: 100000,
  revenueGrowthRates: [0.20, 0.15, 0.12, 0.10, 0.08],
  grossMargin: 0.75,
  sgaPercentOfRev: 0.40,
  taxRate: 0.21,
  dso: 45,
  dio: 30,
  dpo: 60,
  capexPercentOfRev: 0.05,
  daPercentOfCapex: 1.0,
  wacc: 0.12,
  terminalGrowthRate: 0.03,
  sharesOutstanding: 1000,
  netDebt: 50000,
};

export default function Home() {
  const [assumptions, setAssumptions] = useState<Assumptions>(DEFAULT_ASSUMPTIONS);

  const modelOutput = useMemo(() => runDCFModel(assumptions), [assumptions]);
  const { projections, valuation } = modelOutput;

  const handleAssumptionChange = (key: keyof Assumptions, value: any) => {
    setAssumptions(prev => ({ ...prev, [key]: value }));
  };

  const handleGrowthRateChange = (yearIndex: number, value: number) => {
    const newRates = [...assumptions.revenueGrowthRates];
    newRates[yearIndex] = value;
    handleAssumptionChange('revenueGrowthRates', newRates);
  };

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans">
      
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-10">
        <div className="max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white">
              V
            </div>
            <h1 className="text-xl font-bold tracking-tight">Interactive DCF Model</h1>
          </div>
          <div className="text-sm font-medium text-slate-500 bg-slate-100 dark:bg-slate-800 px-3 py-1 rounded-full">
            Institutional Suite
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-6 py-8">
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8 xl:items-start">
          
          {/* LEFT SIDEBAR: Drivers & Assumptions */}
          <div className="xl:col-span-1 space-y-6 lg:sticky lg:top-24">
            
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span className="w-2 h-6 rounded bg-indigo-500 inline-block"></span>
                Base Metrics
              </h2>
              <div className="space-y-4">
                <AssumptionInput
                  label="Year 0 Revenue"
                  format="currency"
                  value={assumptions.year0Revenue}
                  onChange={(v) => handleAssumptionChange('year0Revenue', v)}
                />
                <AssumptionInput
                  label="Net Debt"
                  description="Total Debt minus Cash"
                  format="currency"
                  value={assumptions.netDebt}
                  onChange={(v) => handleAssumptionChange('netDebt', v)}
                />
                <AssumptionInput
                  label="Shares Outstanding"
                  value={assumptions.sharesOutstanding}
                  onChange={(v) => handleAssumptionChange('sharesOutstanding', v)}
                />
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span className="w-2 h-6 rounded bg-blue-500 inline-block"></span>
                Growth & Margin Assumptions
              </h2>
              
              <div className="space-y-4">
                <AssumptionSlider
                  label="Target Gross Margin"
                  value={assumptions.grossMargin}
                  min={0.20} max={0.99} step={0.01}
                  format="percent"
                  onChange={(v) => handleAssumptionChange('grossMargin', v)}
                />
                
                <h3 className="text-sm font-semibold text-slate-500 pt-2 uppercase tracking-wider">Revenue Growth Forecast</h3>
                {assumptions.revenueGrowthRates.map((rate, idx) => (
                  <AssumptionSlider
                    key={idx}
                    label={`Year ${idx + 1} Growth`}
                    value={rate}
                    min={0.01} max={0.50} step={0.01}
                    format="percent"
                    onChange={(v) => handleGrowthRateChange(idx, v)}
                  />
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span className="w-2 h-6 rounded bg-emerald-500 inline-block"></span>
                Capital & Valuation
              </h2>
              <div className="space-y-4">
                <AssumptionSlider
                  label="WACC (Discount Rate)"
                  description="Weighted Average Cost of Capital"
                  value={assumptions.wacc}
                  min={0.05} max={0.20} step={0.005}
                  format="percent"
                  onChange={(v) => handleAssumptionChange('wacc', v)}
                />
                <AssumptionSlider
                  label="Terminal Growth Rate"
                  description="Perpetuity growth past Year 5"
                  value={assumptions.terminalGrowthRate}
                  min={0.01} max={0.05} step={0.001}
                  format="percent"
                  onChange={(v) => handleAssumptionChange('terminalGrowthRate', v)}
                />
                <AssumptionSlider
                  label="Tax Rate"
                  value={assumptions.taxRate}
                  min={0} max={0.4} step={0.01}
                  format="percent"
                  onChange={(v) => handleAssumptionChange('taxRate', v)}
                />
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm hidden xl:block">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span className="w-2 h-6 rounded bg-violet-500 inline-block"></span>
                Working Capital (Days)
              </h2>
              <div className="space-y-4">
                 <AssumptionSlider label="Days Sales Outstanding (DSO)" value={assumptions.dso} min={0} max={120} step={5} format="days" onChange={(v) => handleAssumptionChange('dso', v)} />
                 <AssumptionSlider label="Days Inventory Outstanding (DIO)" value={assumptions.dio} min={0} max={120} step={5} format="days" onChange={(v) => handleAssumptionChange('dio', v)} />
                 <AssumptionSlider label="Days Payable Outstanding (DPO)" value={assumptions.dpo} min={0} max={120} step={5} format="days" onChange={(v) => handleAssumptionChange('dpo', v)} />
              </div>
            </div>

          </div>

          {/* RIGHT MAIN CONTENT: Output */}
          <div className="xl:col-span-3 space-y-8">
            <ScenarioManager 
              currentAssumptions={assumptions}
              onSelectScenario={setAssumptions}
            />

            <ValuationDashboard valuation={valuation} />

            <SensitivityMatrix assumptions={assumptions} />

            <FinancialTable 
              title="Income Statement Projection"
              projections={projections}
              rows={[
                { label: 'Revenue', key: 'revenue', format: 'currency' },
                { label: 'YoY Growth', key: 'yoyGrowth', format: 'percent', emptyYear0: true },
                { label: 'COGS', key: 'cogs', format: 'currency' },
                { label: 'Gross Profit', key: 'grossProfit', format: 'currency', isTotal: true },
                { label: 'Gross Margin', key: 'grossMargin', format: 'percent', isIndent: true },
                { label: 'SG&A', key: 'sga', format: 'currency' },
                { label: 'EBITDA', key: 'ebitda', format: 'currency', isTotal: true },
                { label: 'EBITDA Margin', key: 'ebitdaMargin', format: 'percent', isIndent: true },
                { label: 'Depreciation & Amortization', key: 'depreciation', format: 'currency' },
                { label: 'EBIT', key: 'ebit', format: 'currency', isTotal: true },
                { label: 'Taxes', key: 'taxes', format: 'currency' },
                { label: 'Net Income', key: 'netIncome', format: 'currency', isTotal: true }
              ]}
            />

            <FinancialTable 
              title="Free Cash Flow Build"
              projections={projections}
              rows={[
                { label: 'EBIT', key: 'ebit', format: 'currency' },
                { label: 'Less: Taxes', key: 'taxes', format: 'currency' },
                { label: 'Net Operating Profit After Tax (NOPAT)', key: 'netIncome', format: 'currency', isTotal: true },
                { label: 'Plus: D&A', key: 'depreciation', format: 'currency' },
                { label: 'Less: Capital Expenditures', key: 'capex', format: 'currency' },
                { label: 'Less: Change in Net Working Capital', key: 'changeInNwc', format: 'currency', emptyYear0: true },
                { label: 'Unlevered Free Cash Flow (UFCF)', key: 'unleveredFreeCashFlow', format: 'currency', isTotal: true, emptyYear0: true },
                { label: 'Discount Factor', key: 'discountFactor', format: 'number', emptyYear0: true },
                { label: 'Present Value of UFCF', key: 'presentValueUFCF', format: 'currency', isTotal: true, emptyYear0: true },
              ]}
            />
          </div>

        </div>
      </main>
    </div>
  );
}
