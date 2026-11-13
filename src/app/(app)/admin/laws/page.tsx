import React from 'react';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { AdminLawsClient } from './AdminLawsClient';
import { MeResponse, LawSourceItem, LawItem, LawVersionItem, LawCoverageResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function AdminLawsPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  if (!session) {
    redirect('/login?next=/admin/laws');
  }

  const authHeaders = { Cookie: `complianceos_session=${session}` };

  // Verify platform admin permission
  let me: MeResponse | null = null;
  try {
    const meRes = await fetch(`${API_BASE}/me`, { headers: authHeaders, cache: 'no-store' });
    if (meRes.ok) {
      me = (await meRes.json()) as MeResponse;
    }
  } catch {
    me = null;
  }

  if (!me || !me.user.is_platform_admin) {
    redirect('/');
  }

  let queue: Array<{
    queue_id: string;
    law_id: string;
    reason: string;
    created_at: string;
    law: LawItem;
    version?: LawVersionItem | null;
  }> = [];

  let sources: LawSourceItem[] = [];
  let coverage: LawCoverageResponse | null = null;

  try {
    const [queueRes, sourcesRes, covRes] = await Promise.all([
      fetch(`${API_BASE}/admin/laws/review-queue`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/admin/laws/sources`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/laws/coverage`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (queueRes.ok) {
      const qData = await queueRes.json();
      queue = qData.queue || [];
    }

    if (sourcesRes.ok) {
      const sData = await sourcesRes.json();
      sources = sData.sources || [];
    }

    if (covRes.ok) {
      coverage = await covRes.json();
    }
  } catch (err) {
    console.error('Error fetching admin legal data on server:', err);
  }

  return (
    <AdminLawsClient
      initialQueue={queue}
      initialSources={sources}
      coverage={coverage}
    />
  );
}

