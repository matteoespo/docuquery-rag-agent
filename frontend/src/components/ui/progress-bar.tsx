'use client';

import { motion } from 'framer-motion';

interface ProgressBarProps {
  /** Progress value between 0 and 100. */
  value: number;
  /** Optional label displayed above the bar. */
  label?: string;
}

export function ProgressBar({ value, label }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className="w-full space-y-1.5">
      {/* Header row – label + percentage */}
      <div className="flex items-center justify-between">
        {label && (
          <span className="text-xs font-medium text-zinc-400">{label}</span>
        )}
        <span className="ml-auto text-xs tabular-nums text-zinc-500">
          {Math.round(clamped)}%
        </span>
      </div>

      {/* Track */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
        {/* Filled bar */}
        <motion.div
          className="h-full rounded-full bg-blue-600"
          initial={{ width: 0 }}
          animate={{ width: `${clamped}%` }}
          transition={{ type: 'spring', stiffness: 80, damping: 20 }}
          style={{
            boxShadow: '0 0 10px rgba(37, 99, 235, 0.45), 0 0 4px rgba(37, 99, 235, 0.25)',
          }}
        />
      </div>
    </div>
  );
}
