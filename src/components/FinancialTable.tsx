import React from 'react';
import { FinancialYear } from '../types/finance';

interface FinancialTableProps {
  projections: FinancialYear[];
  title: string;
  rows: {
    label: string;
    key: keyof FinancialYear;
    format: 'currency' | 'percent' | 'number';
    isTotal?: boolean;
    isIndent?: boolean;
    emptyYear0?: boolean; // Sometimes Yr 0 has no value, like YoY growth
  }[];
}

const formatValue = (val: number, format: 'currency' | 'percent' | 'number', emptyYear0 = false, isYear0 = false) => {
  if (isYear0 && emptyYear0) return '-';
  if (isNaN(val)) return '-';
  
  if (format === 'percent') {
    return `${(val * 100).toFixed(1)}%`;
  }
  if (format === 'currency') {
    return val < 0 
      ? `($${Math.abs(val).toLocaleString(undefined, { maximumFractionDigits: 0 })})`
      : `$${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return val.toLocaleString(undefined, { maximumFractionDigits: 1 });
};

export const FinancialTable: React.FC<FinancialTableProps> = ({ projections, title, rows }) => {
  return (
    <div className="w-full overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100">{title}</h3>
      </div>
      <table className="w-full text-sm text-left">
        <thead className="text-xs text-slate-500 dark:text-slate-400 uppercase bg-slate-50 dark:bg-slate-800/50">
          <tr>
            <th className="px-5 py-3 font-medium">Metric</th>
            {projections.map((p) => (
              <th key={p.year} className="px-5 py-3 text-right font-medium">
                {p.year === 0 ? 'Year 0 (Base)' : `Year ${p.year}`}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row, idx) => (
            <tr key={idx} className={`hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${row.isTotal ? 'bg-slate-50/30 dark:bg-slate-800/20 font-semibold' : ''}`}>
              <td className={`px-5 py-3 whitespace-nowrap text-slate-700 dark:text-slate-300 ${row.isIndent ? 'pl-10 text-slate-500 dark:text-slate-400' : ''}`}>
                {row.label}
              </td>
              {projections.map((p) => (
                <td key={p.year} className={`px-5 py-3 text-right tabular-nums ${row.isTotal ? 'text-slate-900 dark:text-slate-100' : 'text-slate-600 dark:text-slate-400'}`}>
                  {formatValue(p[row.key] as number, row.format, row.emptyYear0, p.year === 0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
