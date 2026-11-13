import React from 'react';
import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';
import { LawDiffClient } from './LawDiffClient';
import { LawDetailResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{
    from_version_id?: string;
    to_version_id?: string;
  }>;
}

export default async function LawDiffPage({ params, searchParams }: PageProps) {
  const { id } = await params;
  const sParams = await searchParams;
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  const authHeaders: Record<string, string> = {};
  if (session) {
    authHeaders['Cookie'] = `complianceos_session=${session}`;
  }

  let detail: LawDetailResponse | null = null;
  let diffData: {
    law_id: string;
    from_version_id: string;
    to_version_id: string;
    diffs: Array<{
      number_label: string;
      heading?: string | null;
      change_type: 'added' | 'removed' | 'modified' | 'unchanged';
      old_text?: string | null;
      new_text?: string | null;
    }>;
  } | null = null;

  try {
    const detailRes = await fetch(`${API_BASE}/laws/${encodeURIComponent(id)}`, {
      headers: authHeaders,
      cache: 'no-store',
    });

    if (!detailRes.ok) {
      if (detailRes.status === 404) notFound();
      throw new Error(`Failed to fetch law: HTTP ${detailRes.status}`);
    }

    detail = (await detailRes.json()) as LawDetailResponse;

    // Pick versions: either specified or the two most recent versions
    const versions = detail.versions || [];
    let fromId = sParams.from_version_id;
    let toId = sParams.to_version_id;

    if ((!fromId || !toId) && versions.length >= 2) {
      toId = versions[0].id;
      fromId = versions[1].id;
    } else if ((!fromId || !toId) && versions.length === 1) {
      fromId = versions[0].id;
      toId = versions[0].id;
    }

    if (fromId && toId && fromId !== toId) {
      const diffRes = await fetch(
        `${API_BASE}/laws/${encodeURIComponent(id)}/diff?from_version_id=${encodeURIComponent(
          fromId,
        )}&to_version_id=${encodeURIComponent(toId)}`,
        { headers: authHeaders, cache: 'no-store' },
      );
      if (diffRes.ok) {
        diffData = await diffRes.json();
      }
    }
  } catch (err) {
    console.error('Error fetching law diff on server:', err);
    notFound();
  }

  return (
    <LawDiffClient
      detail={detail}
      diffData={diffData}
      selectedFromId={sParams.from_version_id}
      selectedToId={sParams.to_version_id}
    />
  );
}

