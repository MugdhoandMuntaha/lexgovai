import React from 'react';
import { RegulationsClient } from './RegulationsClient';
import { RegulationDetailResponse, RegulationSummary } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function RegulationsPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialRegulations: RegulationSummary[] = [];
  let initialDetail: RegulationDetailResponse | null = null;

  try {
    const regsRes = await fetch(`${apiBase}/regulations`, {
      headers: authHeaders,
      cache: 'no-store',
    });
    if (regsRes.ok) {
      initialRegulations = (await regsRes.json()) as RegulationSummary[];
    }

    const defaultId = initialRegulations[0]?.id || 'nbr-vat-sro-4.2';
    const detailRes = await fetch(`${apiBase}/regulations/${encodeURIComponent(defaultId)}`, {
      headers: authHeaders,
      cache: 'no-store',
    });
    if (detailRes.ok) {
      initialDetail = (await detailRes.json()) as RegulationDetailResponse;
    }
  } catch (e) {
    console.error('Failed to load regulations catalog on server', e);
  }

  return (
    <RegulationsClient
      initialRegulations={initialRegulations}
      initialDetail={initialDetail}
    />
  );
}
