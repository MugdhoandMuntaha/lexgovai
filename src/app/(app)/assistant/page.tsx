import React from 'react';
import { cookies } from 'next/headers';
import { AssistantClient } from './AssistantClient';
import { AssistantThreadItem, MeResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function AssistantPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let initialThreads: AssistantThreadItem[] = [];
  let canPersistThreads = false;
  let canGroundSop = false;

  if (session) {
    const authHeaders = { Cookie: `complianceos_session=${session}` };
    try {
      const [threadsRes, meRes] = await Promise.all([
        fetch(`${API_BASE}/assistant/threads`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/me`, { headers: authHeaders, cache: 'no-store' }),
      ]);

      if (threadsRes.ok) {
        const tData = await threadsRes.json();
        initialThreads = tData.threads || [];
      }

      if (meRes.ok) {
        const meData = (await meRes.json()) as MeResponse;
        const asstLvl = meData.capabilities?.ai_assistant?.current_level;
        canPersistThreads = asstLvl === 'on';
        canGroundSop = asstLvl === 'on';
      }
    } catch (e) {
      console.error('Failed to load initial assistant telemetry on server', e);
    }
  }

  return (
    <AssistantClient
      initialThreads={initialThreads}
      canPersistThreads={canPersistThreads}
      canGroundSop={canGroundSop}
    />
  );
}
