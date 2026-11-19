'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { getUsage, cancelSubscription, getChecklist, updateChecklistItem } from '@/lib/api';
import { ChecklistItem, UsageMeter as UsageMeterType } from '@/lib/types';
import { useAuth } from '@/context/AuthContext';
import { PlanBadge } from '@/components/PlanBadge';
import { UsageMeter } from '@/components/UsageMeter';
import { Shield, Building, CreditCard, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';

export default function AccountPage() {
  const { user, workspace, subscription, refresh, openUpgradeModal, isLoading: authLoading } = useAuth();
  const [meters, setMeters] = useState<UsageMeterType[]>([]);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCanceling, setIsCanceling] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [usageData, checklistData] = await Promise.all([
        getUsage().catch(() => []),
        getChecklist().catch(() => []),
      ]);
      setMeters(usageData);
      setChecklist(checklistData);
    } catch {
      // Non-fatal
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      getUsage().catch(() => []),
      getChecklist().catch(() => []),
    ]).then(([usageData, checklistData]) => {
      if (mounted) {
        setMeters(usageData);
        setChecklist(checklistData);
        setIsLoading(false);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel your subscription at the end of the current billing cycle?')) {
      return;
    }
    setIsCanceling(true);
    try {
      await cancelSubscription();
      await refresh();
      setMessage('Subscription will be canceled at the end of the billing period.');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to cancel subscription');
    } finally {
      setIsCanceling(false);
    }
  };

  const handleToggleChecklist = async (item: ChecklistItem) => {
    try {
      const updated = await updateChecklistItem(item.id, !item.done);
      setChecklist((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update checklist item');
    }
  };

  if (authLoading || isLoading) {
    return (
      <div className="py-20 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent align-[-0.125em]" />
        <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Loading Account & Workspace Data...
        </p>
      </div>
    );
  }

  const isCanceled = subscription?.cancel_at_period_end;

  return (
    <div className="max-w-5xl mx-auto space-y-8 py-4">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Workspace & Subscription</h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage your workspace plan, view usage limits, and track compliance checklists.
          </p>
        </div>
        <button
          onClick={() => {
            refresh();
            loadData();
          }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {message && (
        <div className="rounded-xl bg-blue-50 border border-blue-200 p-4 text-xs text-blue-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {/* Grid: Workspace Info & Subscription Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Workspace Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-base">
            <Building className="w-5 h-5 text-indigo-600" />
            <h2>Workspace Information</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Workspace Name:</span>
              <span className="font-semibold text-slate-900">{workspace?.name || 'Default Workspace'}</span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Workspace ID:</span>
              <span className="font-mono text-slate-700 text-[11px]">{workspace?.id}</span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Account Owner:</span>
              <span className="font-semibold text-slate-900">{user?.email}</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-slate-500">Member Role:</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                Owner
              </span>
            </div>
          </div>
        </div>

        {/* Subscription Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-900 font-bold text-base">
              <CreditCard className="w-5 h-5 text-indigo-600" />
              <h2>Current Plan</h2>
            </div>
            <PlanBadge planId={subscription?.plan_id} size="md" />
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Subscription Status:</span>
              <span
                className={`font-semibold capitalize ${
                  isCanceled ? 'text-amber-600' : 'text-emerald-600'
                }`}
              >
                {isCanceled ? 'Canceling at Period End' : subscription?.status || 'Active'}
              </span>
            </div>
            {subscription?.period_end && (
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">
                  {isCanceled ? 'Access Ends On:' : 'Next Renewal Date:'}
                </span>
                <span className="font-semibold text-slate-900">
                  {new Date(subscription.period_end).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>

          <div className="pt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => openUpgradeModal('Account Plan Management')}
              className="flex-1 rounded-xl bg-indigo-600 py-2 px-3 text-xs font-semibold text-white hover:bg-indigo-500 shadow-xs text-center"
            >
              {subscription?.plan_id === 'free' ? 'Upgrade Plan' : 'Change Plan'}
            </button>

            {subscription?.plan_id !== 'free' && !isCanceled && (
              <button
                type="button"
                onClick={handleCancel}
                disabled={isCanceling}
                className="rounded-xl border border-rose-200 bg-rose-50 py-2 px-3 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
              >
                {isCanceling ? 'Canceling...' : 'Cancel Subscription'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Usage Meters Section */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-5">
        <div>
          <h2 className="text-base font-bold text-slate-900">Usage Metering & Monthly Quotas</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time usage counters across Bangladesh SME compliance pipeline capabilities.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {meters.map((meter) => (
            <div key={meter.metric} className="rounded-xl border border-slate-100 bg-slate-50/50 p-4">
              <UsageMeter meter={meter} showResets />
            </div>
          ))}
        </div>
      </div>

      {/* Checklist Section (if items exist) */}
      {checklist.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-600" />
            <h2 className="text-base font-bold text-slate-900">Personalized Compliance Action Items</h2>
          </div>
          <p className="text-xs text-slate-500">
            Action items generated from your Start Fresh guided questionnaire.
          </p>

          <div className="divide-y divide-slate-100">
            {checklist.map((item) => (
              <div key={item.id} className="py-3 flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={item.done}
                  onChange={() => handleToggleChecklist(item)}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600 cursor-pointer"
                />
                <div className="flex-1 text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-semibold ${
                        item.done ? 'line-through text-slate-400' : 'text-slate-900'
                      }`}
                    >
                      {item.title}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 uppercase">
                      {item.tier.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-slate-500 mt-0.5">{item.reason}</p>
                </div>
                {item.done && (
                  <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Done</span>
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
