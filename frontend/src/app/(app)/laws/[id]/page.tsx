import React from 'react';
import { notFound } from 'next/navigation';
import { LawDetailClient } from './LawDetailClient';
import { LawDetailResponse, LawSectionItem } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function LawDetailPage({ params }: PageProps) {
  const { id } = await params;
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let detail: LawDetailResponse | null = null;
  let sections: LawSectionItem[] = [];

  try {
    const [detailRes, sectionsRes] = await Promise.all([
      fetch(`${apiBase}/laws/${encodeURIComponent(id)}`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/laws/${encodeURIComponent(id)}/sections`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (!detailRes.ok) {
      if (detailRes.status === 404) {
        notFound();
      }
      throw new Error(`Failed to fetch law ${id}: HTTP ${detailRes.status}`);
    }

    detail = (await detailRes.json()) as LawDetailResponse;

    if (sectionsRes.ok) {
      const secData = await sectionsRes.json();
      sections = secData.sections || [];
    }
  } catch (err) {
    console.error('Error fetching law details on server:', err);
    notFound();
  }

  if (!detail) {
    notFound();
  }

  return <LawDetailClient detail={detail} initialSections={sections} />;
}
