import React from 'react';
import { SupportClient } from './SupportClient';
import { MeResponse, SupportTicketItem } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function SupportPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let initialTickets: SupportTicketItem[] = [];
  let userPlanId = 'free';
  let userName = '';
  let userEmail = '';

  try {
    const [ticketsRes, meRes] = await Promise.all([
      fetch(`${apiBase}/support/tickets`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
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

  return (
    <SupportClient
      initialTickets={initialTickets}
      userPlanId={userPlanId}
      userName={userName}
      userEmail={userEmail}
    />
  );
}
