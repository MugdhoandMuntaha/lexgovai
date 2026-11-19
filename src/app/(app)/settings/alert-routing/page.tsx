import React from 'react';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';
import { AlertRoutingClient } from './AlertRoutingClient';
import { MeResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function AlertRoutingPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let complianceOwners: any[] = [];
  let settings: any = {};
  let teamMembers: any[] = [];
  let deliveryStats: any = {};
  let userRole = 'member';

  try {
    const [ownersRes, settingsRes, teamRes, statsRes, meRes] = await Promise.all([
      fetch(`${apiBase}/alerts/compliance-owners`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/alerts/workspace-settings`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/team/members`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/alerts/stats`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (ownersRes.ok) {
      const data = await ownersRes.json();
      complianceOwners = data.compliance_owners || [];
    }

    if (settingsRes.ok) {
      const data = await settingsRes.json();
      settings = data.settings || {};
    }

    if (teamRes.ok) {
      const data = await teamRes.json();
      teamMembers = data.members || [];
    }

    if (statsRes.ok) {
      const data = await statsRes.json();
      deliveryStats = data.delivery_stats || {};
    }

    if (meRes.ok) {
      const data = (await meRes.json()) as MeResponse;
      userRole = data.workspace?.role || 'member';
    }
  } catch (err) {
    console.error('Failed to load alert routing configuration on server:', err);
  }

  return (
    <AlertRoutingClient
      initialOwners={complianceOwners}
      initialSettings={settings}
      teamMembers={teamMembers}
      initialStats={deliveryStats}
      userRole={userRole}
    />
  );
}
