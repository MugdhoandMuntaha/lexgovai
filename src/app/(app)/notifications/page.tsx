import React from 'react';
import { NotificationsClient } from './NotificationsClient';
import { NotificationItem } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function NotificationsPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialNotifications: NotificationItem[] = [];
  let initialUnreadCount = 0;

  try {
    const res = await fetch(`${apiBase}/notifications`, {
      headers: authHeaders,
      cache: 'no-store',
    });
    if (res.ok) {
      const data = await res.json();
      initialNotifications = data.notifications || [];
      initialUnreadCount = data.unread_count || 0;
    }
  } catch (e) {
    console.error('Failed to fetch initial notifications', e);
  }

  return (
    <NotificationsClient
      initialNotifications={initialNotifications}
      initialUnreadCount={initialUnreadCount}
    />
  );
}
