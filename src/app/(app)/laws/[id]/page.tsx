import React from 'react';
import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';
import { LawDetailClient } from './LawDetailClient';
import { LawDetailResponse, LawSectionItem } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function LawDetailPage({ params }: PageProps) {
  const { id } = await params;
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  const authHeaders: Record<string, string> = {};
  if (session) {
    authHeaders['Cookie'] = `complianceos_session=${session}`;
  }

  let detail: LawDetailResponse | null = null;
  let sections: LawSectionItem[] = [];

  try {
    const [detailRes, sectionsRes] = await Promise.all([
      fetch(`${API_BASE}/laws/${encodeURIComponent(id)}`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${API_BASE}/laws/${encodeURIComponent(id)}/sections`, { headers: authHeaders, cache: 'no-store' }),
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

  return <LawDetailClient detail={detail} initialSections={sections} />;
}

