import React from 'react';
import { Assumptions } from '../types/finance';

interface ScenarioManagerProps {
  currentAssumptions: Assumptions;
  onSelectScenario: (assumptions: Assumptions) => void;
}

export const SCENARIOS: { name: string; description: string; assumptions: Assumptions; color: string }[] = [
  {
    name: 'Base Case',
    description: 'Moderate growth and standard margin assumptions.',
    color: 'from-blue-500 to-indigo-600',
    assumptions: {
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
    }
  },
  {
    name: 'Upside Case',
    description: 'High revenue growth, improved efficiency, and lower discount rate.',
    color: 'from-emerald-500 to-teal-600',
    assumptions: {
      year0Revenue: 100000,
      revenueGrowthRates: [0.28, 0.24, 0.20, 0.16, 0.12],
      grossMargin: 0.80,
      sgaPercentOfRev: 0.35,
      taxRate: 0.21,
      dso: 40,
      dio: 25,
      dpo: 65,
      capexPercentOfRev: 0.06,
      daPercentOfCapex: 1.0,
      wacc: 0.10,
      terminalGrowthRate: 0.035,
      sharesOutstanding: 1000,
      netDebt: 50000,
    }
  },
  {
    name: 'Downside Case',
    description: 'Stagnating growth, compressed margin, and higher discount rate.',
    color: 'from-rose-500 to-red-600',
    assumptions: {
      year0Revenue: 100000,
      revenueGrowthRates: [0.10, 0.07, 0.05, 0.03, 0.02],
      grossMargin: 0.68,
      sgaPercentOfRev: 0.45,
      taxRate: 0.21,
      dso: 50,
      dio: 35,
      dpo: 55,
      capexPercentOfRev: 0.04,
      daPercentOfCapex: 1.0,
      wacc: 0.14,
      terminalGrowthRate: 0.02,
      sharesOutstanding: 1000,
      netDebt: 50000,
    }
  }
];

export const ScenarioManager: React.FC<ScenarioManagerProps> = ({ currentAssumptions, onSelectScenario }) => {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm">
      <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
        <span className="w-2 h-6 rounded bg-violet-500 inline-block"></span>
        Valuation Scenario Presets
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {SCENARIOS.map((scenario) => {
          // Check if current assumptions match the scenario assumptions
          const isSelected = 
            Math.abs(currentAssumptions.wacc - scenario.assumptions.wacc) < 0.0001 &&
            Math.abs(currentAssumptions.grossMargin - scenario.assumptions.grossMargin) < 0.0001 &&
            Math.abs(currentAssumptions.terminalGrowthRate - scenario.assumptions.terminalGrowthRate) < 0.0001 &&
            currentAssumptions.revenueGrowthRates[0] === scenario.assumptions.revenueGrowthRates[0];

          return (
            <button
              key={scenario.name}
              onClick={() => onSelectScenario(scenario.assumptions)}
              className={`text-left p-4 rounded-xl border transition-all ${
                isSelected 
                  ? 'border-transparent bg-slate-900 text-white dark:bg-slate-800 ring-2 ring-violet-500' 
                  : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white/50 dark:bg-slate-800/50 text-slate-800 dark:text-slate-200'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`text-sm font-bold ${isSelected ? 'text-violet-400' : 'text-slate-900 dark:text-white'}`}>
                  {scenario.name}
                </span>
                {isSelected && (
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-violet-500/20 text-violet-300">
                    Active
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {scenario.description}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
