'use client';

import React from 'react';
import { PlanId } from '@/lib/types';

interface PlanBadgeProps {
  planId?: PlanId | string | null;
  size?: 'sm' | 'md';
}

const PLAN_STYLES: Record<string, { label: string; classes: string }> = {
  free: {
    label: 'Free',
    classes: 'bg-slate-100 text-slate-700 border-slate-300',
  },
  starter: {
    label: 'Starter',
    classes: 'bg-blue-50 text-blue-700 border-blue-300',
  },
  growth: {
    label: 'Growth',
    classes: 'bg-emerald-50 text-emerald-700 border-emerald-300',
  },
  professional: {
    label: 'Professional',
    classes: 'bg-purple-50 text-purple-700 border-purple-300',
  },
};

export function PlanBadge({ planId = 'free', size = 'md' }: PlanBadgeProps) {
  const current = PLAN_STYLES[planId || 'free'] || PLAN_STYLES.free;
  const sizeClasses =
    size === 'sm' ? 'text-xs px-2 py-0.5 font-medium' : 'text-xs px-2.5 py-1 font-semibold';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${current.classes} ${sizeClasses}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {current.label}
    </span>
  );
}

