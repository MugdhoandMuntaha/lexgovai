import React from 'react';
import { AssistantClient } from './AssistantClient';
import { AssistantThreadItem, MeResponse } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function AssistantPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialThreads: AssistantThreadItem[] = [];
  let canPersistThreads = false;
  let canGroundSop = false;

  try {
    const [threadsRes, meRes] = await Promise.all([
      fetch(`${apiBase}/assistant/threads`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
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

  return (
    <AssistantClient
      initialThreads={initialThreads}
      canPersistThreads={canPersistThreads}
      canGroundSop={canGroundSop}
    />
  );
}
