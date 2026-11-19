'use client';

import React from 'react';
import { UsageMeter as UsageMeterType } from '@/lib/types';

interface UsageMeterProps {
  meter: UsageMeterType;
  showResets?: boolean;
}

export function UsageMeter({ meter, showResets = true }: UsageMeterProps) {
  const isZeroLimit = meter.limit === 0;
  const isHigh = meter.percent_used >= 80;

  const barColor = isZeroLimit
    ? 'bg-slate-300'
    : isHigh
    ? 'bg-rose-500'
    : meter.percent_used >= 50
    ? 'bg-amber-500'
    : 'bg-emerald-500';

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-700">{meter.display_name}</span>
        <span className="font-mono text-slate-500">
          {isZeroLimit ? (
            <span className="text-slate-400">0 / 0 (Locked)</span>
          ) : (
            `${meter.used} / ${meter.limit}`
          )}
        </span>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full transition-all duration-300 ${barColor}`}
          style={{ width: `${isZeroLimit ? 0 : Math.min(meter.percent_used, 100)}%` }}
        />
      </div>

      {showResets && meter.resets_at && (
        <div className="flex justify-end text-[10px] text-slate-400">
          Resets on {new Date(meter.resets_at).toLocaleDateString()}
        </div>
      )}
    </div>
  );
}

