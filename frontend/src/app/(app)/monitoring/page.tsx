import React from 'react';
import { MonitoringClient } from './MonitoringClient';
import { MeResponse, MonitoredSourceItem, MonitoredSubscriptionItem } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function MonitoringPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialSources: MonitoredSourceItem[] = [];
  let initialSubscriptions: MonitoredSubscriptionItem[] = [];
  let canSubscribe = false;
  let quotaLimit = 0;

  try {
    const [sourcesRes, subsRes, meRes] = await Promise.all([
      fetch(`${apiBase}/monitoring/sources`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/monitoring/subscriptions`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (sourcesRes.ok) {
      const sData = await sourcesRes.json();
      initialSources = sData.sources || [];
    }
    if (subsRes.ok) {
      const subData = await subsRes.json();
      initialSubscriptions = subData.subscriptions || [];
    }
    if (meRes.ok) {
      const meData = (await meRes.json()) as MeResponse;
      const alertsLvl = meData.capabilities?.personalized_alerts?.current_level;
      canSubscribe = alertsLvl !== 'off';
      quotaLimit = meData.limits?.monitored_sources || 0;
    }
  } catch (e) {
    console.error('Failed to load initial monitoring data on server', e);
  }

  return (
    <MonitoringClient
      initialSources={initialSources}
      initialSubscriptions={initialSubscriptions}
      canSubscribe={canSubscribe}
      quotaLimit={quotaLimit}
    />
  );
}
