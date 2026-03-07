import React from 'react';

interface AssumptionSliderProps {
  label: string;
  value: number;
  onChange: (val: number) => void;
  min: number;
  max: number;
  step: number;
  format?: 'percent' | 'currency' | 'number' | 'days';
  description?: string;
}

export const AssumptionSlider: React.FC<AssumptionSliderProps> = ({
  label,
  value,
  onChange,
  min,
  max,
  step,
  format = 'number',
  description
}) => {
  const displayValue = React.useMemo(() => {
    switch (format) {
      case 'percent':
        return `${(value * 100).toFixed(1)}%`;
      case 'currency':
        return `$${value.toLocaleString()}`;
      case 'days':
        return `${value} days`;
      default:
        return value.toString();
    }
  }, [value, format]);

  return (
    <div className="flex flex-col gap-2 p-3 bg-white/50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-blue-400 dark:hover:border-blue-500 transition-colors">
      <div className="flex justify-between items-center">
        <div>
          <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">{label}</label>
          {description && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{description}</p>
          )}
        </div>
        <span className="text-sm font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-1 rounded">
          {displayValue}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer dark:bg-slate-700 accent-blue-600"
      />
    </div>
  );
};
