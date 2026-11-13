'use client';

import React, { useState, useTransition } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  Plus,
  Radio,
  Trash2,
} from 'lucide-react';
import { subscribeMonitor, unsubscribeMonitor } from '@/lib/api';
import { MonitoredSourceItem, MonitoredSubscriptionItem } from '@/lib/types';
import { useAuth } from '@/context/AuthContext';

interface Props {
  initialSources: MonitoredSourceItem[];
  initialSubscriptions: MonitoredSubscriptionItem[];
  canSubscribe: boolean;
  quotaLimit: number;
}

export function MonitoringClient({
  initialSources,
  initialSubscriptions,
  canSubscribe,
  quotaLimit,
}: Props) {
  const { openUpgradeModal } = useAuth();
  const [sources] = useState<MonitoredSourceItem[]>(initialSources);
  const [subscriptions, setSubscriptions] = useState<MonitoredSubscriptionItem[]>(initialSubscriptions);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const isSubscribed = (regId: string) => subscriptions.some((s) => s.regulation_id === regId);
  const usageCount = subscriptions.length;
  const isAtQuota = usageCount >= quotaLimit;

  const handleSubscribe = (regId: string) => {
    if (!canSubscribe) {
      openUpgradeModal('Continuous Regulatory Monitoring', 'starter');
      return;
    }
    if (isAtQuota) {
      setErrorMsg(`You have reached your limit of ${quotaLimit} monitored source(s). Upgrade to Growth or Professional to monitor more sources.`);
      return;
    }

    startTransition(async () => {
      setErrorMsg(null);
      try {
        const sub = await subscribeMonitor(regId);
        setSubscriptions((prev) => [sub, ...prev]);
        setSuccessMsg('Successfully subscribed to continuous monitoring alerts.');
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to subscribe.');
      }
    });
  };

  const handleUnsubscribe = (regId: string) => {
    startTransition(async () => {
      setErrorMsg(null);
      try {
        await unsubscribeMonitor(regId);
        setSubscriptions((prev) => prev.filter((s) => s.regulation_id !== regId));
        setSuccessMsg('Source removed from active monitoring.');
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to unsubscribe.');
      }
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold mb-2 border border-emerald-200">
            <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600" />
            <span>Continuous Watcher Surveillance</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Monitored Regulatory Sources</h1>
          <p className="text-sm text-slate-600 mt-1 max-w-2xl">
            Automated crawlers poll official government gazettes, SRO repositories, and trade authority feeds. When statutory clauses change, automated diffs and impact analyses dispatch immediately.
          </p>
        </div>

        {/* Quota Card */}
        <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs flex items-center gap-4 shrink-0">
          <div>
            <span className="text-xs font-medium text-slate-500">Monitored Quota</span>
            <div className="flex items-baseline gap-1 mt-0.5">
              <span className="text-xl font-black text-slate-900">{usageCount}</span>
              <span className="text-xs text-slate-400">/ {canSubscribe ? quotaLimit : 0} sources</span>
            </div>
          </div>
          {!canSubscribe && (
            <button
              type="button"
              onClick={() => openUpgradeModal('Continuous Regulatory Monitoring', 'starter')}
              className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-xs"
            >
              Unlock
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-600 font-bold">×</button>
        </div>
      )}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-600 font-bold">×</button>
        </div>
      )}

      {/* Free Plan Lock Banner */}
      {!canSubscribe && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 border border-indigo-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-indigo-600" />
              <h3 className="text-sm font-bold text-slate-900">Automated Source Monitoring is Locked</h3>
            </div>
            <p className="text-xs text-slate-600 max-w-xl">
              Free plans include access to the curated Regulatory News Feed. Upgrade to Starter, Growth, or Professional to activate real-time web crawlers, email notifications, and automated multi-agent SOP impact analyses.
            </p>
          </div>
          <button
            type="button"
            onClick={() => openUpgradeModal('Continuous Regulatory Monitoring', 'starter')}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-xs shrink-0"
          >
            Upgrade Plan
          </button>
        </div>
      )}

      {/* Source Catalog */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-slate-900">Available Regulatory Gazette Streams</h2>

        <div className="grid gap-4">
          {sources.map((src) => {
            const subscribed = isSubscribed(src.regulation_id);
            const isFailing = src.status === 'failing';

            return (
              <div
                key={src.id}
                className="bg-white p-6 rounded-2xl border border-slate-200/90 hover:border-slate-300 shadow-xs transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">{src.regulation_title}</span>
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[10px] font-semibold border border-slate-200">
                      {src.sector}
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[10px] font-medium border border-slate-200">
                      {src.jurisdiction}
                    </span>
                    {/* Honest Health Status */}
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium ${
                        isFailing
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {isFailing ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                      <span>
                        {isFailing
                          ? `Source error: ${src.last_error}`
                          : src.last_checked
                          ? `Polled ${new Date(src.last_checked).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                          : 'Awaiting scheduled crawl'}
                      </span>
                    </span>
                  </div>

                  <p className="text-xs text-slate-500 font-mono">
                    Endpoint: {src.url || 'Official Regulatory Gazette Portal'}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {subscribed ? (
                    <button
                      type="button"
                      onClick={() => handleUnsubscribe(src.regulation_id)}
                      disabled={isPending}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Unsubscribe</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleSubscribe(src.regulation_id)}
                      disabled={isPending || (!canSubscribe && false)}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-all shadow-xs"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Subscribe & Monitor</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
