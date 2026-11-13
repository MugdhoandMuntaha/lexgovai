import React from 'react';
import { cookies } from 'next/headers';
import { LawsClient } from './LawsClient';
import { LawItem, LawCoverageResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

interface PageProps {
  searchParams: Promise<{
    q?: string;
    law_type?: string;
    domain_tag?: string;
    status?: string;
    year?: string;
    page?: string;
  }>;
}

export default async function LawsPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  const authHeaders: Record<string, string> = {};
  if (session) {
    authHeaders['Cookie'] = `complianceos_session=${session}`;
  }

  let laws: LawItem[] = [];
  let total = 0;
  let coverage: LawCoverageResponse | null = null;
  let recommended: Array<{ law: LawItem; reason: string }> = [];

  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.law_type) qs.set('law_type', params.law_type);
  if (params.domain_tag) qs.set('domain_tag', params.domain_tag);
  if (params.status) qs.set('status', params.status);
  if (params.year) qs.set('year', params.year);
  if (params.page) qs.set('page', params.page);

  try {
    const [lawsRes, covRes, recRes] = await Promise.all([
      fetch(`${API_BASE}/laws?${qs.toString()}`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/laws/coverage`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/laws/recommended`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (lawsRes.ok) {
      const data = await lawsRes.json();
      laws = data.laws || [];
      total = data.total ?? laws.length;
    }

    if (covRes.ok) {
      coverage = await covRes.json();
    }

    if (recRes.ok) {
      const recData = await recRes.json();
      recommended = recData.recommended || [];
    }
  } catch (err) {
    console.error('Failed to fetch legal library on server:', err);
  }

  return (
    <LawsClient
      initialLaws={laws}
      totalCount={total}
      coverage={coverage}
      recommended={recommended}
      currentParams={params}
    />
  );
}

