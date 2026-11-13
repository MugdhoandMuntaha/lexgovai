import React from 'react';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { AdminClient } from './AdminClient';
import {
  MeResponse,
  QueueStats,
  RegulationSourceAdmin,
  RegulationVersionAdmin,
  SupportTicketAdmin,
} from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function AdminPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  if (!session) {
    redirect('/login?next=/admin');
  }

  // Check admin rights via /me
  let me: MeResponse | null = null;
  try {
    const meRes = await fetch(`${API_BASE}/me`, {
      headers: { Cookie: `complianceos_session=${session}` },
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

  const authHeaders = { Cookie: `complianceos_session=${session}` };

  try {
    const [qRes, vRes, sRes, tRes] = await Promise.all([
      fetch(`${API_BASE}/admin/queue`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/admin/regulations/pending`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/admin/sources`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/admin/support/tickets`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (qRes.ok) initialQueue = await qRes.json();
    if (vRes.ok) {
      const vData = await vRes.json();
      initialVersions = vData.versions || [];
    }
    if (sRes.ok) initialSources = await sRes.json();
    if (tRes.ok) initialTickets = await tRes.json();
  } catch (e) {
    console.error('Failed to load initial admin telemetry on server', e);
  }

  return (
    <AdminClient
      initialQueue={initialQueue}
      initialVersions={initialVersions}
      initialSources={initialSources}
      initialTickets={initialTickets}
    />
  );
}
