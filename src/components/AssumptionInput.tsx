import React, { useState, useEffect } from 'react';

interface AssumptionInputProps {
  label: string;
  value: number;
  onChange: (val: number) => void;
  format?: 'currency' | 'number';
  description?: string;
  min?: number;
}

export const AssumptionInput: React.FC<AssumptionInputProps> = ({
  label,
  value,
  onChange,
  format = 'number',
  description,
  min = 0
}) => {
  const [localValue, setLocalValue] = useState<string>(value.toString());

  // Sync with external value changes (e.g. resets)
  useEffect(() => {
    setLocalValue(value.toString());
  }, [value]);

  const handleBlur = () => {
    let parsed = parseFloat(localValue);
    if (isNaN(parsed) || parsed < min) {
      parsed = min;
    }
    setLocalValue(parsed.toString());
    onChange(parsed);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Basic validation to only allow numbers and decimals
    const val = e.target.value.replace(/[^0-9.-]/g, '');
    setLocalValue(val);
  };

  return (
    <div className="flex flex-col gap-2 p-3 bg-white/50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-blue-400 dark:hover:border-blue-500 transition-colors">
      <div className="flex flex-col mb-1">
        <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">{label}</label>
        {description && (
          <span className="text-xs text-slate-500 dark:text-slate-400">{description}</span>
        )}
      </div>
      
      <div className="relative flex items-center">
        {format === 'currency' && (
          <span className="absolute left-3 text-slate-500 font-medium">$</span>
        )}
        <input
          type="text" // Use text so we can control formatting more strictly
          value={localValue}
          onChange={handleChange}
          onBlur={handleBlur}
          className={`w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium ${
            format === 'currency' ? 'pl-7 pr-3' : 'px-3'
          }`}
        />
      </div>
    </div>
  );
};
