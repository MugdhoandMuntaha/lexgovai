import React from 'react';
import { ApiKeysClient } from './ApiKeysClient';
import { ApiKeyItem, MeResponse } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function ApiKeysPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialKeys: ApiKeyItem[] = [];
  let canManageApiKeys = false;
  let userPlanId = 'free';
  let currentUserRole = 'member';

  try {
    const [keysRes, meRes] = await Promise.all([
      fetch(`${apiBase}/settings/api-keys`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (keysRes.ok) {
      initialKeys = (await keysRes.json()) as ApiKeyItem[];
    }
    if (meRes.ok) {
      const meData = (await meRes.json()) as MeResponse;
      userPlanId = meData.subscription?.plan_id || 'free';
      currentUserRole = meData.workspace?.role || 'member';
      const apiCap = meData.capabilities?.api_integrations?.current_level;
      canManageApiKeys = apiCap !== 'off';
    }
  } catch (e) {
    console.error('Failed to load initial API keys on server', e);
  }

  return (
    <ApiKeysClient
      initialKeys={initialKeys}
      canManageApiKeys={canManageApiKeys}
      userPlanId={userPlanId}
      currentUserRole={currentUserRole}
    />
  );
}
