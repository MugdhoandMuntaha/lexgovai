'use client';

import React, { useEffect, useState } from 'react';
import { getPlans, createCheckout } from '@/lib/api';
import { PlanItem, PlanCapabilityItem, PlanId } from '@/lib/types';
import { useAuth } from '@/context/AuthContext';
import { PlanBadge } from '@/components/PlanBadge';
import { Check, Clock, Sparkles } from 'lucide-react';

export default function PricingPage() {
  const { subscription, refresh, user } = useAuth();
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionPlanId, setActionPlanId] = useState<PlanId | null>(null);

  useEffect(() => {
    let mounted = true;
    getPlans()
      .then((data) => {
        if (!mounted) return;
        // Normalize array or object response
        const plansList = Array.isArray(data)
          ? data
          : data && typeof data === 'object' && 'plans' in data
          ? Object.values((data as { plans: Record<string, PlanItem> }).plans)
          : [];
        setPlans(plansList);
        setError(null);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to load plans');
        setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleUpgrade = async (planId: PlanId) => {
    if (!user) {
      window.location.href = `/signup?redirect=/pricing`;
      return;
    }
    setActionPlanId(planId);
    try {
      const res = await createCheckout(planId);
      await refresh();
      if (res.checkout_url && !res.checkout_url.includes('mock=true')) {
        window.location.href = res.checkout_url;
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Checkout failed');
    } finally {
      setActionPlanId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="py-20 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent align-[-0.125em]" />
        <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Loading Subscription Plans...
        </p>
      </div>
    );
  }

  if (error || plans.length === 0) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-700">
        {error || 'Unable to load plan catalog.'}
      </div>
    );
  }

  const currentPlan = subscription?.plan_id || 'free';

  // Group capabilities by category from the first plan definition
  const capabilitiesList: PlanCapabilityItem[] = plans[0]?.capabilities || [];
  const categories: Record<string, PlanCapabilityItem[]> = {};

  capabilitiesList.forEach((cap) => {
    const cat = cap.category || 'General';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(cap);
  });

  return (
    <div className="space-y-12 py-6">
      {/* Header */}
      <div className="text-center max-w-3xl mx-auto space-y-3">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200/60 text-indigo-700 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Transparent Pricing for Bangladeshi Enterprises</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
          Automate Compliance at Any Scale
        </h1>
        <p className="text-base text-slate-600">
          From first-time founders launching an SME to high-volume corporations reconciling complex NBR VAT requirements.
        </p>
      </div>

      {/* Plan Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {plans.map((plan) => {
          const pid = plan.id;
          const isCurrent = currentPlan === pid;
          const isPro = pid === 'professional';
          const isGrowth = pid === 'growth';

          return (
            <div
              key={pid}
              className={`relative flex flex-col rounded-2xl bg-white p-6 shadow-sm border transition-all ${
                isGrowth
                  ? 'border-indigo-600 ring-2 ring-indigo-600/20'
                  : isPro
                  ? 'border-purple-300'
                  : 'border-slate-200'
              }`}
            >
              {plan.badge && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-3 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-xs">
                  {plan.badge}
                </div>
              )}

              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900">{plan.name}</h3>
                <PlanBadge planId={pid} size="sm" />
              </div>

              <p className="mt-2 text-xs text-slate-500 min-h-[32px]">{plan.description}</p>

              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-3xl font-extrabold text-slate-900">
                  ৳{plan.price_bdt_monthly.toLocaleString()}
                </span>
                <span className="text-xs text-slate-500 font-medium">/ month</span>
              </div>

              <div className="mt-3 rounded-lg bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-600 border border-slate-100">
                Personalization: <span className="font-semibold text-slate-900">{plan.personalization_label}</span>
              </div>

              <div className="mt-6 flex-1 space-y-4">
                <div>
                  <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Key Quotas</h4>
                  <ul className="mt-2 space-y-1.5 text-xs text-slate-600">
                    <li className="flex items-center justify-between">
                      <span>Detailed Analyses:</span>
                      <span className="font-semibold text-slate-900 font-mono">
                        {plan.limits.detailed_analyses || '0'}/mo
                      </span>
                    </li>
                    <li className="flex items-center justify-between">
                      <span>SOP Documents:</span>
                      <span className="font-semibold text-slate-900 font-mono">
                        {plan.limits.sop_documents || '0'}
                      </span>
                    </li>
                    <li className="flex items-center justify-between">
                      <span>Audit History:</span>
                      <span className="font-semibold text-slate-900 font-mono">
                        {plan.audit_history_days ? `${plan.audit_history_days} days` : 'Immediate only'}
                      </span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="mt-8 pt-4 border-t border-slate-100">
                {isCurrent ? (
                  <button
                    disabled
                    className="w-full rounded-xl bg-slate-100 py-2.5 text-xs font-semibold text-slate-500 cursor-not-allowed"
                  >
                    Current Plan
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleUpgrade(pid)}
                    disabled={actionPlanId === pid}
                    className={`w-full rounded-xl py-2.5 text-xs font-semibold transition-all shadow-xs ${
                      isGrowth || isPro
                        ? 'bg-indigo-600 text-white hover:bg-indigo-500'
                        : 'bg-slate-900 text-white hover:bg-slate-800'
                    }`}
                  >
                    {actionPlanId === pid
                      ? 'Processing...'
                      : pid === 'free'
                      ? 'Downgrade to Free'
                      : `Upgrade to ${plan.name}`}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Complete Capability Matrix Table */}
      <div className="mt-16 space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-slate-900">Full Capability & Feature Matrix</h2>
          <p className="mt-1 text-xs text-slate-500">
            Compare all 23 platform capabilities side-by-side
          </p>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-700">
              <tr>
                <th className="py-3.5 px-4 font-bold w-1/3">Capability</th>
                {plans.map((p) => (
                  <th key={p.id} className="py-3.5 px-4 font-bold text-center">
                    {p.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {Object.entries(categories).map(([category, caps]) => (
                <React.Fragment key={category}>
                  <tr className="bg-slate-50/70">
                    <td
                      colSpan={plans.length + 1}
                      className="py-2 px-4 font-bold text-[11px] uppercase tracking-wider text-slate-500"
                    >
                      {category}
                    </td>
                  </tr>
                  {caps.map((cap) => (
                    <tr key={cap.key} className="hover:bg-slate-50/40">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                          <span>{cap.display_name}</span>
                          {!cap.implemented && (
                            <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-50 px-2 py-0.5 text-[9px] font-semibold text-amber-700 border border-amber-200">
                              <Clock className="w-2.5 h-2.5" />
                              <span>Coming soon</span>
                            </span>
                          )}
                        </div>
                        {cap.description && (
                          <p className="text-[11px] text-slate-500">{cap.description}</p>
                        )}
                      </td>
                      {plans.map((p) => {
                        const planCap = p.capabilities.find((c) => c.key === cap.key);
                        const level = planCap?.level || 'off';
                        const isOff = level === 'off';
                        const isOn = level === 'on';

                        return (
                          <td key={p.id} className="py-3 px-4 text-center">
                            {isOn ? (
                              <Check className="mx-auto h-4 w-4 text-emerald-600" />
                            ) : isOff ? (
                              <span className="text-slate-300 font-bold">—</span>
                            ) : (
                              <span className="font-medium text-slate-700 capitalize bg-slate-100 px-2 py-0.5 rounded-full text-[10px]">
                                {level}
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
