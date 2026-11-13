import React from 'react';
import { cookies } from 'next/headers';
import { CoverageClient } from './CoverageClient';
import { LawCoverageResponse, MeResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function LawsCoveragePage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  const authHeaders: Record<string, string> = {};
  if (session) {
    authHeaders['Cookie'] = `complianceos_session=${session}`;
  }

  let coverage: LawCoverageResponse | null = null;
  let me: MeResponse | null = null;

  try {
    const [covRes, meRes] = await Promise.all([
      fetch(`${API_BASE}/laws/coverage`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/me`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (covRes.ok) {
      coverage = (await covRes.json()) as LawCoverageResponse;
    }

    if (meRes.ok) {
      me = (await meRes.json()) as MeResponse;
    }
  } catch (err) {
    console.error('Error fetching coverage stats on server:', err);
  }

  return <CoverageClient coverage={coverage} isPlatformAdmin={Boolean(me?.user?.is_platform_admin)} />;
}

