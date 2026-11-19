import React from 'react';
import { TeamClient } from './TeamClient';
import { MeResponse, TeamInviteItem, TeamMembersResponse } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function TeamPage() {
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

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

  try {
    const [membersRes, invitesRes, meRes] = await Promise.all([
      fetch(`${apiBase}/team/members`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/team/invites`, { headers: authHeaders, cache: 'no-store' }),
      fetch(`${apiBase}/me`, { headers: authHeaders, cache: 'no-store' }),
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
