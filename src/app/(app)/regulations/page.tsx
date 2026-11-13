import React from 'react';
import { cookies } from 'next/headers';
import { RegulationsClient } from './RegulationsClient';
import { RegulationDetailResponse, RegulationSummary } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function RegulationsPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let initialRegulations: RegulationSummary[] = [];
  let initialDetail: RegulationDetailResponse | null = null;

  if (session) {
    const authHeaders = { Cookie: `complianceos_session=${session}` };
    try {
      const regsRes = await fetch(`${API_BASE}/regulations`, {
        headers: authHeaders,
        cache: 'no-store',
      });
      if (regsRes.ok) {
        initialRegulations = (await regsRes.json()) as RegulationSummary[];
      }

      const defaultId = initialRegulations[0]?.id || 'nbr-vat-sro-4.2';
      const detailRes = await fetch(`${API_BASE}/regulations/${encodeURIComponent(defaultId)}`, {
        headers: authHeaders,
        cache: 'no-store',
      });
      if (detailRes.ok) {
        initialDetail = (await detailRes.json()) as RegulationDetailResponse;
      }
    } catch (e) {
      console.error('Failed to load regulations catalog on server', e);
    }
  }

  return (
    <RegulationsClient
      initialRegulations={initialRegulations}
      initialDetail={initialDetail}
    />
  );
}
