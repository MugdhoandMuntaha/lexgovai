'use client';

import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { createCheckout } from '@/lib/api';
import { PlanId } from '@/lib/types';
import { PlanBadge } from './PlanBadge';

const PLAN_INFO: Record<PlanId, { name: string; price: number; desc: string; highlights: string[] }> = {
  free: {
    name: 'Free',
    price: 0,
    desc: 'General, questionnaire-based guidance',
    highlights: ['Launch questionnaire', 'General policy suggestions', 'Basic company profile'],
  },
  starter: {
    name: 'Starter',
    price: 999,
    desc: 'Basic company-specific compliance automation',
    highlights: [
      'SOP upload & document indexing',
      '10 detailed analyses / month',
      '5 SOP documents',
      'Basic personalized checklist',
      'Markdown audit reports',
    ],
  },
  growth: {
    name: 'Growth',
    price: 2999,
    desc: 'Document-based continuous compliance',
    highlights: [
      '50 detailed analyses / month',
      '25 SOP documents',
      'Technical operational fixes',
      'Full policy drafts',
      '365-day audit history',
    ],
  },
  professional: {
    name: 'Professional',
    price: 7999,
    desc: 'Continuous and advanced enterprise compliance',
    highlights: [
      '200 detailed analyses / month',
      '100 SOP documents',
      'Advanced technical fixes & policy drafts',
      '1,095-day (3-year) audit retention',
      'Priority support',
    ],
  },
};

export function UpgradeModal() {
  const { upgradeModalState, closeUpgradeModal, refresh, subscription } = useAuth();
  const [selectedPlan, setSelectedPlan] = useState<PlanId>(
    upgradeModalState.requiredPlan || 'starter',
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!upgradeModalState.isOpen) return null;

  const currentPlan = subscription?.plan_id || 'free';
  const plans: PlanId[] = ['starter', 'growth', 'professional'];

  const handleCheckout = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await createCheckout(selectedPlan);
      setSuccess(true);
      await refresh();
      setTimeout(() => {
        setSuccess(false);
        closeUpgradeModal();
      }, 1200);
      if (res.checkout_url && !res.checkout_url.includes('mock=true')) {
        window.location.href = res.checkout_url;
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Checkout failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
      <div className="relative w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl ring-1 ring-slate-900/10">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Upgrade Your Plan</h2>
            <p className="text-sm text-slate-500">
              {upgradeModalState.featureName
                ? `To unlock "${upgradeModalState.featureName}", select an upgraded plan below.`
                : 'Select the right plan for your business compliance operations.'}
            </p>
          </div>
          <button
            onClick={closeUpgradeModal}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700 border border-rose-200">
            {error}
          </div>
        )}

        {success ? (
          <div className="my-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="mt-3 text-lg font-semibold text-slate-900">Plan Upgraded!</h3>
            <p className="text-sm text-slate-500">Your workspace is now on the {PLAN_INFO[selectedPlan].name} plan.</p>
          </div>
        ) : (
          <>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3">
              {plans.map((p) => {
                const info = PLAN_INFO[p];
                const isCurrent = currentPlan === p;
                const isSelected = selectedPlan === p;

                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setSelectedPlan(p)}
                    disabled={isCurrent}
                    className={`relative text-left rounded-xl border p-4 transition-all ${
                      isSelected
                        ? 'border-indigo-600 ring-2 ring-indigo-600/20 bg-indigo-50/20'
                        : isCurrent
                        ? 'border-slate-200 bg-slate-50 opacity-60 cursor-not-allowed'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <PlanBadge planId={p} size="sm" />
                      {isCurrent && <span className="text-[10px] font-medium text-slate-500">Current</span>}
                    </div>

                    <div className="mt-3">
                      <div className="text-lg font-bold text-slate-900">
                        ৳{info.price.toLocaleString()}
                        <span className="text-xs font-normal text-slate-500">/mo</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500 line-clamp-2">{info.desc}</p>
                    </div>

                    <ul className="mt-3 space-y-1 text-[11px] text-slate-600">
                      {info.highlights.slice(0, 3).map((h, i) => (
                        <li key={i} className="flex items-center gap-1.5">
                          <span className="text-indigo-600 font-bold">✓</span>
                          <span>{h}</span>
                        </li>
                      ))}
                    </ul>
                  </button>
                );
              })}
            </div>

            <div className="mt-6 flex items-center justify-between pt-4 border-t border-slate-100">
              <div className="text-xs text-slate-500">
                Mock payment mode active • Simulated instant activation
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={closeUpgradeModal}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={isSubmitting || selectedPlan === currentPlan}
                  onClick={handleCheckout}
                  className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-xs hover:bg-indigo-500 disabled:opacity-50"
                >
                  {isSubmitting ? 'Processing...' : `Upgrade to ${PLAN_INFO[selectedPlan].name}`}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

