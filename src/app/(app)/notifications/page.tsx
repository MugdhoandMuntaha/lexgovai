import React from 'react';
import { cookies } from 'next/headers';
import { NotificationsClient } from './NotificationsClient';
import { NotificationItem } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function NotificationsPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let initialNotifications: NotificationItem[] = [];
  let initialUnreadCount = 0;

  if (session) {
    try {
      const res = await fetch(`${API_BASE}/notifications`, {
        headers: {
          Cookie: `complianceos_session=${session}`,
        },
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
  }

  return (
    <NotificationsClient
      initialNotifications={initialNotifications}
      initialUnreadCount={initialUnreadCount}
    />
  );
}
