import React from 'react';
import { cookies } from 'next/headers';
import { ApiKeysClient } from './ApiKeysClient';
import { ApiKeyItem, MeResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function ApiKeysPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let initialKeys: ApiKeyItem[] = [];
  let canManageApiKeys = false;
  let userPlanId = 'free';
  let currentUserRole = 'member';

  if (session) {
    const authHeaders = { Cookie: `complianceos_session=${session}` };
    try {
      const [keysRes, meRes] = await Promise.all([
        fetch(`${API_BASE}/settings/api-keys`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/me`, { headers: authHeaders, cache: 'no-store' }),
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
