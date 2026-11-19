import React from 'react';
import { CoverageClient } from './CoverageClient';
import { LawCoverageResponse, MeResponse } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function LawsCoveragePage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let coverage: LawCoverageResponse | null = null;
  let me: MeResponse | null = null;

  try {
    const [covRes, meRes] = await Promise.all([
      fetch(`${apiBase}/laws/coverage`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
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
