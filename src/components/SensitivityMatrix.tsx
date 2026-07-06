import React from 'react';
import { Assumptions } from '../types/finance';
import { runDCFModel } from '../lib/financeEngine';

interface SensitivityMatrixProps {
  assumptions: Assumptions;
}

export const SensitivityMatrix: React.FC<SensitivityMatrixProps> = ({ assumptions }) => {
  const waccOffsets = [-0.02, -0.01, 0, 0.01, 0.02];
  const tgrOffsets = [-0.01, -0.005, 0, 0.005, 0.01];

  const waccList = waccOffsets.map(offset => assumptions.wacc + offset);
  const tgrList = tgrOffsets.map(offset => assumptions.terminalGrowthRate + offset);

  const calculateCell = (wacc: number, tgr: number) => {
    // Return implied share price for a given WACC and Terminal Growth Rate
    const result = runDCFModel({
      ...assumptions,
      wacc,
      terminalGrowthRate: tgr
    });
    return result.valuation.impliedSharePrice;
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm overflow-hidden">
      <div className="mb-4">
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100">Sensitivity Analysis: Implied Share Price</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Sensitivity of share price to changes in Discount Rate (WACC) vs. Terminal Growth Rate.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs text-center border-collapse">
          <thead>
            <tr>
              <th className="p-2 border-b border-slate-200 dark:border-slate-800 text-left font-bold text-slate-400">
                WACC \ TGR
              </th>
              {tgrList.map((tgr, idx) => (
                <th key={idx} className="p-2 border-b border-slate-200 dark:border-slate-800 font-semibold text-slate-600 dark:text-slate-300">
                  {(tgr * 100).toFixed(1)}%
                  {tgr === assumptions.terminalGrowthRate && <span className="block text-[9px] text-blue-500 font-bold">(Current)</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {waccList.map((wacc, wIdx) => {
              const isCurrentWacc = Math.abs(wacc - assumptions.wacc) < 0.0001;
              return (
                <tr key={wIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                  <td className="p-2 text-left font-semibold text-slate-600 dark:text-slate-300 border-r border-slate-100 dark:border-slate-800">
                    {(wacc * 100).toFixed(1)}%
                    {isCurrentWacc && <span className="inline-block ml-1 text-[9px] text-blue-500 font-bold">(Current)</span>}
                  </td>
                  {tgrList.map((tgr, tIdx) => {
                    const price = calculateCell(wacc, tgr);
                    const isCurrentTgr = Math.abs(tgr - assumptions.terminalGrowthRate) < 0.0001;
                    const isCenter = isCurrentWacc && isCurrentTgr;

                    return (
                      <td
                        key={tIdx}
                        className={`p-3 border border-slate-100 dark:border-slate-800 font-medium tabular-nums ${
                          isCenter
                            ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 font-bold ring-2 ring-blue-500/30'
                            : 'text-slate-700 dark:text-slate-400'
                        }`}
                      >
                        ${price.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
