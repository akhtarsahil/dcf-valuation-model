import React from 'react';
import { ValuationOutput } from '../types/finance';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { TrendingUp, DollarSign, Building2, Landmark } from 'lucide-react';

interface ValuationDashboardProps {
  valuation: ValuationOutput;
}

const formatCurrency = (val: number) => `$${(val / 1000).toFixed(1)}M`;
const formatExactCurrency = (val: number) => `$${val.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

export const ValuationDashboard: React.FC<ValuationDashboardProps> = ({ valuation }) => {
  // Waterfall chart data for Enterprise Value -> Equity Value
  const chartData = [
    { name: 'PV of UFCF', val: valuation.npvOfUFCF, fill: '#3b82f6' }, // blue-500
    { name: 'PV of Terminal', val: valuation.pvOfTerminalValue, fill: '#8b5cf6' }, // violet-500
    { name: 'Enterprise Value', val: valuation.enterpriseValue, fill: '#14b8a6' }, // teal-500
    { name: 'Less: Net Debt', val: -valuation.netDebt, fill: '#ef4444' }, // red-500
    { name: 'Equity Value', val: valuation.equityValue, fill: '#10b981' }, // emerald-500
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
      {/* Implied Share Price Card (Hero) */}
      <div className="lg:col-span-1 bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 rounded-full bg-blue-500/20 blur-2xl"></div>
        <div className="absolute bottom-0 left-0 -ml-8 -mb-8 w-32 h-32 rounded-full bg-emerald-500/20 blur-2xl"></div>
        
        <h2 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Implied Share Price</h2>
        <div className="flex items-baseline gap-2 mb-6">
          <span className="text-5xl font-black tracking-tight">{formatExactCurrency(valuation.impliedSharePrice)}</span>
          <span className="text-slate-400 text-sm">/ share</span>
        </div>
        
        <div className="space-y-4">
          <div className="flex justify-between items-center pb-3 border-b border-slate-700/50">
            <div className="flex items-center gap-2 text-slate-300">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span className="text-sm">Equity Value</span>
            </div>
            <span className="font-semibold">{formatExactCurrency(valuation.equityValue)}</span>
          </div>
          <div className="flex justify-between items-center pb-3 border-b border-slate-700/50">
            <div className="flex items-center gap-2 text-slate-300">
              <Building2 className="w-4 h-4 text-teal-400" />
              <span className="text-sm">Enterprise Value</span>
            </div>
            <span className="font-semibold">{formatExactCurrency(valuation.enterpriseValue)}</span>
          </div>
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2 text-slate-300">
              <Landmark className="w-4 h-4 text-red-400" />
              <span className="text-sm">Net Debt</span>
            </div>
            <span className="font-semibold text-slate-400">{formatExactCurrency(valuation.netDebt)}</span>
          </div>
        </div>
      </div>

      {/* Waterfall Chart */}
      <div className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-6">Valuation Bridge</h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} dy={10} />
              <YAxis tickFormatter={formatCurrency} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} dx={-10} />
              <Tooltip 
                formatter={(value: any) => formatExactCurrency(value as number)}
                cursor={{ fill: '#f1f5f9', opacity: 0.1 }}
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              />
              <Bar dataKey="val" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
