import React from 'react';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';
import { NotificationsSettingsClient } from './NotificationsSettingsClient';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function NotificationsSettingsPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialPreferences: Record<string, Record<string, boolean>> = {};
  let catalog: string[] = [];
  let channelsData: any = null;

  try {
    const [prefsRes, channelsRes] = await Promise.all([
      fetch(`${apiBase}/alerts/preferences`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/alerts/channels`, { headers: authHeaders, cache: 'no-store' }),
    ]);

    if (prefsRes.ok) {
      const pData = await prefsRes.json();
      initialPreferences = pData.preferences || {};
      catalog = pData.catalog || [];
    }

    if (channelsRes.ok) {
      channelsData = await channelsRes.json();
    }
  } catch (err) {
    console.error('Failed to load notification settings on server:', err);
  }

  return (
    <NotificationsSettingsClient
      initialPreferences={initialPreferences}
      catalog={catalog}
      initialChannels={channelsData}
    />
  );
}
