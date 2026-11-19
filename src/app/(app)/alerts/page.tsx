import React from 'react';
import { AlertsClient } from './AlertsClient';
import { AlertItem } from '@/lib/api';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';
import { MeResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

interface PageProps {
  searchParams: Promise<{
    status?: string;
    severity?: string;
  }>;
}

export default async function AlertsPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialAlerts: AlertItem[] = [];
  let userRole = 'member';
  let channelsData: any = null;

  const qs = new URLSearchParams();
  if (params.status) qs.set('status', params.status);
  if (params.severity) qs.set('severity', params.severity);

  try {
    const [alertsRes, meRes, chRes] = await Promise.all([
      fetch(`${apiBase}/alerts?${qs.toString()}`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/alerts/channels`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (alertsRes.ok) {
      const data = await alertsRes.json();
      initialAlerts = data.alerts || [];
    }

    if (meRes.ok) {
      const meData = (await meRes.json()) as MeResponse;
      userRole = meData.workspace?.role || 'member';
    }

    if (chRes.ok) {
      channelsData = await chRes.json();
    }
  } catch (err) {
    console.error('Failed to load alerts on server:', err);
  }

  return (
    <AlertsClient
      initialAlerts={initialAlerts}
      userRole={userRole}
      channelsData={channelsData}
      currentParams={params}
    />
  );
}
