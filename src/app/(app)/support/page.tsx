import React from 'react';
import { cookies } from 'next/headers';
import { SupportClient } from './SupportClient';
import { MeResponse, SupportTicketItem } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function SupportPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let initialTickets: SupportTicketItem[] = [];
  let userPlanId = 'free';
  let userName = '';
  let userEmail = '';

  if (session) {
    const authHeaders = { Cookie: `complianceos_session=${session}` };
    try {
      const [ticketsRes, meRes] = await Promise.all([
        fetch(`${API_BASE}/support/tickets`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/me`, { headers: authHeaders, cache: 'no-store' }),
      ]);

      if (ticketsRes.ok) {
        initialTickets = (await ticketsRes.json()) as SupportTicketItem[];
      }
      if (meRes.ok) {
        const meData = (await meRes.json()) as MeResponse;
        userPlanId = meData.subscription?.plan_id || 'free';
        userName = meData.user?.full_name || '';
        userEmail = meData.user?.email || '';
      }
    } catch (e) {
      console.error('Failed to load initial support data on server', e);
    }
  }

  return (
    <SupportClient
      initialTickets={initialTickets}
      userPlanId={userPlanId}
      userName={userName}
      userEmail={userEmail}
    />
  );
}
