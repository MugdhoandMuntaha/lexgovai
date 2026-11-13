import React from 'react';
import { cookies } from 'next/headers';
import { TeamClient } from './TeamClient';
import { MeResponse, TeamInviteItem, TeamMembersResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export default async function TeamPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let initialTeamData: TeamMembersResponse = {
    members: [],
    seat_limit: 1,
    active_count: 1,
    total_count: 1,
  };
  let initialInvites: TeamInviteItem[] = [];
  let currentUserId = '';
  let currentUserRole = 'member';
  let canInvite = false;
  let userPlanId = 'free';

  if (session) {
    const authHeaders = { Cookie: `complianceos_session=${session}` };
    try {
      const [membersRes, invitesRes, meRes] = await Promise.all([
        fetch(`${API_BASE}/team/members`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/team/invites`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/me`, { headers: authHeaders, cache: 'no-store' }),
      ]);

      if (membersRes.ok) {
        initialTeamData = (await membersRes.json()) as TeamMembersResponse;
      }
      if (invitesRes.ok) {
        initialInvites = (await invitesRes.json()) as TeamInviteItem[];
      }
      if (meRes.ok) {
        const meData = (await meRes.json()) as MeResponse;
        currentUserId = meData.user?.id || '';
        currentUserRole = meData.workspace?.role || 'member';
        userPlanId = meData.subscription?.plan_id || 'free';
        const teamCap = meData.capabilities?.team_collaboration?.current_level;
        canInvite = teamCap === 'on';
      }
    } catch (e) {
      console.error('Failed to load initial team data on server', e);
    }
  }

  return (
    <TeamClient
      initialMembers={initialTeamData.members}
      seatLimit={initialTeamData.seat_limit}
      activeCount={initialTeamData.active_count}
      initialInvites={initialInvites}
      currentUserId={currentUserId}
      currentUserRole={currentUserRole}
      canInvite={canInvite}
      userPlanId={userPlanId}
    />
  );
}
