import React from 'react';
import { redirect } from 'next/navigation';
import { AdminClient } from './AdminClient';
import {
  MeResponse,
  QueueStats,
  RegulationVersionAdmin,
  RegulationSourceAdmin,
  SupportTicketAdmin,
} from '@/lib/types';
import { AdminUserItem } from '@/lib/api';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function AdminPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  // Check admin rights via /me
  let me: MeResponse | null = null;
  try {
    const meRes = await fetch(`${apiBase}/me`, {
      headers: authHeaders,
      cache: 'no-store',
    });
    if (meRes.ok) {
      me = (await meRes.json()) as MeResponse;
    }
  } catch {
    me = null;
  }

  if (!me || !me.user.is_platform_admin) {
    redirect('/');
  }

  // Fetch admin telemetry on server
  let initialQueue: QueueStats | null = null;
  let initialVersions: RegulationVersionAdmin[] = [];
  let initialSources: RegulationSourceAdmin[] = [];
  let initialTickets: SupportTicketAdmin[] = [];
  let initialUsers: AdminUserItem[] = [];

  try {
    const [qRes, vRes, sRes, tRes, uRes] = await Promise.all([
      fetch(`${apiBase}/admin/queue`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/admin/regulations/pending`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/admin/sources`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/admin/support/tickets`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/admin/users`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (qRes.ok) initialQueue = await qRes.json();
    if (vRes.ok) {
      const vData = await vRes.json();
      initialVersions = vData.versions || [];
    }
    if (sRes.ok) initialSources = await sRes.json();
    if (tRes.ok) initialTickets = await tRes.json();
    if (uRes.ok) {
      const uData = await uRes.json();
      initialUsers = uData.users || [];
    }
  } catch (err) {
    console.error('Failed to load admin telemetry on server:', err);
  }

  return (
    <AdminClient
      initialQueue={initialQueue}
      initialVersions={initialVersions}
      initialSources={initialSources}
      initialTickets={initialTickets}
      initialUsers={initialUsers}
    />
  );
}
