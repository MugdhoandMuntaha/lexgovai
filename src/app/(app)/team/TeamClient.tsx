'use client';

import React, { useState, useTransition } from 'react';
import Link from 'next/link';
import {
  Users,
  UserPlus,
  Shield,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  Clock,
  Sparkles,
  ArrowRight,
  Lock,
} from 'lucide-react';
import { TeamInviteItem, TeamMemberItem } from '@/lib/types';
import { createTeamInvite, removeTeamMember, revokeTeamInvite, updateTeamMemberRole } from '@/lib/api';

interface TeamClientProps {
  initialMembers: TeamMemberItem[];
  seatLimit: number;
  activeCount: number;
  initialInvites: TeamInviteItem[];
  currentUserId: string;
  currentUserRole: string;
  canInvite: boolean;
  userPlanId: string;
}

export function TeamClient({
  initialMembers,
  seatLimit,
  activeCount: initialActiveCount,
  initialInvites,
  currentUserId,
  currentUserRole,
  canInvite,
  userPlanId,
}: TeamClientProps) {
  const [members, setMembers] = useState<TeamMemberItem[]>(initialMembers);
  const [invites, setInvites] = useState<TeamInviteItem[]>(initialInvites);
  const [activeCount, setActiveCount] = useState<number>(initialActiveCount);

  // Modal / form state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'member' | 'viewer'>('member');
  const [createdInviteUrl, setCreatedInviteUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [isPending, startTransition] = useTransition();

  const isOwner = currentUserRole === 'owner';
  const isAdmin = currentUserRole === 'admin' || isOwner;
  const isSingleUserPlan = seatLimit <= 1;
  const seatsFull = activeCount >= seatLimit;

  const handleSendInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setErrorMsg(null);

    startTransition(async () => {
      try {
        const res = await createTeamInvite(inviteEmail.trim(), inviteRole);
        const inviteUrl = `${window.location.origin}/login?invite=${encodeURIComponent(res.token)}`;
        setCreatedInviteUrl(inviteUrl);
        setInvites((prev) => [
          {
            id: res.id,
            workspace_id: '',
            email: res.email,
            role: res.role as 'admin' | 'member' | 'viewer',
            expires_at: res.expires_at,
            created_at: new Date().toISOString(),
            accepted_at: null,
            revoked_at: null,
          },
          ...prev,
        ]);
        setActiveCount((prev) => prev + 1);
        setInviteEmail('');
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to send invite.');
      }
    });
  };

  const handleRevokeInvite = (inviteId: string) => {
    if (!confirm('Are you sure you want to revoke this invitation?')) return;
    startTransition(async () => {
      try {
        await revokeTeamInvite(inviteId);
        setInvites((prev) => prev.filter((i) => i.id !== inviteId));
        setActiveCount((prev) => Math.max(1, prev - 1));
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Failed to revoke invite.');
      }
    });
  };

  const handleRoleChange = (targetUserId: string, newRole: 'admin' | 'member' | 'viewer') => {
    startTransition(async () => {
      try {
        await updateTeamMemberRole(targetUserId, newRole);
        setMembers((prev) =>
          prev.map((m) => (m.user_id === targetUserId ? { ...m, role: newRole, effective_role: newRole } : m))
        );
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Failed to update member role.');
      }
    });
  };

  const handleRemoveMember = (targetUserId: string, memberEmail: string) => {
    if (!confirm(`Are you sure you want to remove ${memberEmail} from this workspace?`)) return;
    startTransition(async () => {
      try {
        await removeTeamMember(targetUserId);
        setMembers((prev) => prev.filter((m) => m.user_id !== targetUserId));
        setActiveCount((prev) => Math.max(1, prev - 1));
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Failed to remove member.');
      }
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="flex items-center gap-2 text-indigo-600 font-semibold text-xs tracking-wider uppercase mb-1">
            <Users className="w-4 h-4" />
            <span>Workspace Governance</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Team Collaboration</h1>
          <p className="text-sm text-slate-600 mt-1">
            Manage workspace members, assign role-based permissions, and invite compliance colleagues.
          </p>
        </div>

        {isAdmin && (
          <div>
            {canInvite && !seatsFull ? (
              <button
                type="button"
                onClick={() => {
                  setCreatedInviteUrl(null);
                  setErrorMsg(null);
                  setShowInviteModal(true);
                }}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-xs transition-all"
              >
                <UserPlus className="w-4 h-4" />
                <span>Invite Member</span>
              </button>
            ) : (
              <Link
                href="/pricing"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-semibold text-sm shadow-xs transition-all"
              >
                <Sparkles className="w-4 h-4" />
                <span>{isSingleUserPlan ? 'Upgrade to Invite' : 'Expand Seats'}</span>
              </Link>
            )}
          </div>
        )}
      </div>

      {/* Seat Meter Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-700">Seat Utilization</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Active team members + pending invitations count towards plan capacity.
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-extrabold text-slate-900">{activeCount}</span>
              <span className="text-sm font-semibold text-slate-500"> / {seatLimit} seats</span>
            </div>
          </div>

          <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                activeCount >= seatLimit ? 'bg-amber-500' : 'bg-emerald-600'
              }`}
              style={{ width: `${Math.min(100, (activeCount / Math.max(1, seatLimit)) * 100)}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
            <span>Current plan: <strong className="capitalize text-slate-700">{userPlanId}</strong></span>
            <span>{Math.max(0, seatLimit - activeCount)} seats remaining</span>
          </div>
        </div>

        {/* Plan Upgrade Card */}
        <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-50/70 via-white to-slate-50 border border-indigo-100 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-indigo-700 font-bold text-xs uppercase tracking-wider mb-1">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Multi-User Plans</span>
            </div>
            <h3 className="text-base font-bold text-slate-900">Need more seats?</h3>
            <p className="text-xs text-slate-600 mt-1">
              Growth tier includes <strong>3 seats</strong> with RBAC. Professional includes <strong>10 seats</strong> with audit logging.
            </p>
          </div>
          <Link
            href="/pricing"
            className="mt-4 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition-all shadow-xs"
          >
            <span>View All Plans</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* Members Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h2 className="text-base font-bold text-slate-900">Active Members ({members.length})</h2>
          <span className="text-xs text-slate-500 font-medium">Sorted by join date (seniority)</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50/80 text-xs font-semibold uppercase text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3.5">Member</th>
                <th className="px-6 py-3.5">Assigned Role</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5">Joined</th>
                {isAdmin && <th className="px-6 py-3.5 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {members.map((member) => {
                const isMemberOwner = member.role === 'owner';
                const isSelf = member.user_id === currentUserId;

                return (
                  <tr key={member.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">
                        {member.full_name || member.email.split('@')[0]}
                        {isSelf && (
                          <span className="ml-2 text-[10px] bg-slate-100 text-slate-600 font-mono px-1.5 py-0.5 rounded border border-slate-200">
                            YOU
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500">{member.email}</div>
                    </td>

                    <td className="px-6 py-4">
                      {isOwner && !isMemberOwner ? (
                        <select
                          value={member.role}
                          disabled={isPending}
                          onChange={(e) =>
                            handleRoleChange(member.user_id, e.target.value as 'admin' | 'member' | 'viewer')
                          }
                          className="text-xs font-semibold rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                          <option value="admin">Admin</option>
                          <option value="member">Member</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      ) : (
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${
                            member.role === 'owner'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : member.role === 'admin'
                              ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                              : member.role === 'member'
                              ? 'bg-sky-50 text-sky-700 border border-sky-200'
                              : 'bg-slate-100 text-slate-600 border border-slate-200'
                          }`}
                        >
                          <Shield className="w-3 h-3" />
                          <span>{member.role}</span>
                        </span>
                      )}
                    </td>

                    <td className="px-6 py-4">
                      {member.is_frozen ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                          <Lock className="w-3 h-3" />
                          <span>Frozen (Seat Overflow)</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <Check className="w-3 h-3" />
                          <span>Active</span>
                        </span>
                      )}
                    </td>

                    <td className="px-6 py-4 text-xs text-slate-500 font-mono">
                      {member.created_at ? new Date(member.created_at).toLocaleDateString() : 'N/A'}
                    </td>

                    {isAdmin && (
                      <td className="px-6 py-4 text-right">
                        {!isMemberOwner && !isSelf && (
                          <button
                            type="button"
                            onClick={() => handleRemoveMember(member.user_id, member.email)}
                            disabled={isPending}
                            title="Remove member"
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pending Invitations Table */}
      {isAdmin && invites.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <h2 className="text-base font-bold text-slate-900">Pending Invitations ({invites.length})</h2>
            <span className="text-xs text-slate-500 font-medium">Invites expire after 7 days</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50/80 text-xs font-semibold uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3.5">Invited Email</th>
                  <th className="px-6 py-3.5">Assigned Role</th>
                  <th className="px-6 py-3.5">Expires</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invites.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-4 font-semibold text-slate-900">{inv.email}</td>
                    <td className="px-6 py-4 capitalize font-medium text-slate-700">{inv.role}</td>
                    <td className="px-6 py-4 text-xs text-slate-500 font-mono">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span>{new Date(inv.expires_at).toLocaleDateString()}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleRevokeInvite(inv.id)}
                        disabled={isPending}
                        className="text-xs font-semibold text-rose-600 hover:text-rose-700 hover:underline"
                      >
                        Revoke Invite
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">Invite Team Member</h3>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {!createdInviteUrl ? (
              <form onSubmit={handleSendInvite} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="colleague@company.com.bd"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Workspace Role
                  </label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as 'admin' | 'member' | 'viewer')}
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="member">Member - Can run analyses, check tasks, and comment</option>
                    <option value="viewer">Viewer - Read-only access to audit reports and news</option>
                    <option value="admin">Admin - Can manage sources, members, and API keys</option>
                  </select>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowInviteModal(false)}
                    className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isPending || !inviteEmail.trim()}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
                  >
                    {isPending ? 'Sending...' : 'Send Invitation'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
                  Invitation created! An email was dispatched to the recipient. You can also share the single-use invite link directly:
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={createdInviteUrl}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 text-xs font-mono text-slate-700 select-all"
                  />
                  <button
                    type="button"
                    onClick={() => copyToClipboard(createdInviteUrl)}
                    className="px-3 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold flex items-center gap-1.5 shrink-0 hover:bg-slate-800"
                  >
                    {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setShowInviteModal(false)}
                    className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
