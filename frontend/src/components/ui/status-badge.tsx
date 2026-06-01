import type { JSX } from 'react';

type Status = 'ready' | 'waiting' | 'processing' | 'error';

interface StatusBadgeProps {
  status: Status;
}

const statusConfig: Record<
  Status,
  { label: string; dot: string; bg: string; text: string; pulse: boolean }
> = {
  ready: {
    label: 'Ready',
    dot: 'bg-emerald-500',
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    pulse: false,
  },
  waiting: {
    label: 'Waiting',
    dot: 'bg-amber-500',
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    pulse: false,
  },
  processing: {
    label: 'Processing',
    dot: 'bg-blue-500',
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    pulse: true,
  },
  error: {
    label: 'Error',
    dot: 'bg-red-500',
    bg: 'bg-red-500/10',
    text: 'text-red-400',
    pulse: false,
  },
};

export function StatusBadge({ status }: StatusBadgeProps): JSX.Element {
  const cfg = statusConfig[status];

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${cfg.bg} ${cfg.text}`}
    >
      <span className="relative flex h-2 w-2">
        {cfg.pulse && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${cfg.dot}`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${cfg.dot}`} />
      </span>
      {cfg.label}
    </span>
  );
}
