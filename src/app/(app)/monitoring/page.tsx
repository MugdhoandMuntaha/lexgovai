import React from 'react';
import { cookies } from 'next/headers';
import { MonitoringClient } from './MonitoringClient';
import { MeResponse, MonitoredSourceItem, MonitoredSubscriptionItem } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function MonitoringPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let initialSources: MonitoredSourceItem[] = [];
  let initialSubscriptions: MonitoredSubscriptionItem[] = [];
  let canSubscribe = false;
  let quotaLimit = 0;

  if (session) {
    const authHeaders = { Cookie: `complianceos_session=${session}` };
    try {
      const [sourcesRes, subsRes, meRes] = await Promise.all([
        fetch(`${API_BASE}/monitoring/sources`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/monitoring/subscriptions`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/me`, { headers: authHeaders, cache: 'no-store' }),
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
