'use client';

import React, { ReactNode } from 'react';
import { useAuth } from '@/context/AuthContext';
import { PlanId } from '@/lib/types';
import { PlanBadge } from './PlanBadge';

interface FeatureGateProps {
  capability: string;
  minLevel?: string;
  featureName: string;
  requiredPlan?: PlanId;
  children: ReactNode;
  fallback?: ReactNode;
}

export function FeatureGate({
  capability,
  minLevel = 'on',
  featureName,
  requiredPlan = 'starter',
  children,
  fallback,
}: FeatureGateProps) {
  const { hasCapability, openUpgradeModal, isLoading } = useAuth();

  if (isLoading) {
    return <div className="animate-pulse rounded-xl bg-slate-100 p-8 min-h-[160px]" />;
  }

  const allowed = hasCapability(capability, minLevel);

  if (allowed) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
          />
        </svg>
      </div>

      <div className="mt-3 flex items-center justify-center gap-2">
        <h3 className="text-base font-semibold text-slate-900">{featureName} is locked</h3>
        <PlanBadge planId={requiredPlan} size="sm" />
      </div>

      <p className="mx-auto mt-1.5 max-w-sm text-sm text-slate-500">
        This feature requires the {requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1)} plan or higher. Upgrade to unlock full compliance automation.
      </p>

      <div className="mt-5">
        <button
          type="button"
          onClick={() => openUpgradeModal(featureName, requiredPlan)}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
        >
          <span>Upgrade to {requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1)}</span>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </button>
      </div>
    </div>
  );
}

