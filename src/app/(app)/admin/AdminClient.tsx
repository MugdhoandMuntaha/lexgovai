'use client';

import React, { useState, useTransition } from 'react';
import {
  Activity,
  CheckCircle2,
  Clock,
  Layers,
  Newspaper,
  RefreshCw,
  Shield,
  Ticket,
  Users,
  Trash2,
  KeyRound,
  UserCog,
  PlusCircle,
  Crown,
} from 'lucide-react';
import {
  getAdminQueue,
  getAdminPendingRegulations,
  publishAdminRegulationVersion,
  rejectAdminRegulationVersion,
  getAdminSources,
  triggerSourcePoll,
  createAdminNews,
  getAdminTickets,
  updateAdminTicket,
  getAdminUsers,
  createAdminUser,
  updateAdminUser,
  resetAdminUserPassword,
  deleteAdminUser,
  AdminUserItem,
} from '@/lib/api';
import {
  QueueStats,
  RegulationSourceAdmin,
  RegulationVersionAdmin,
  SupportTicketAdmin,
} from '@/lib/types';

type TabKey = 'queue' | 'regulations' | 'sources' | 'news' | 'tickets' | 'users';

const PLAN_OPTIONS = ['free', 'starter', 'growth', 'professional'];
const ROLE_OPTIONS = ['viewer', 'member', 'admin', 'owner'];

interface Props {
  initialQueue: QueueStats | null;
  initialVersions: RegulationVersionAdmin[];
  initialSources: RegulationSourceAdmin[];
  initialTickets: SupportTicketAdmin[];
  initialUsers: AdminUserItem[];
}

export function AdminClient({
  initialQueue,
  initialVersions,
  initialSources,
  initialTickets,
  initialUsers,
}: Props) {
  const [tab, setTab] = useState<TabKey>('queue');
  const [isPending, startTransition] = useTransition();

  // Data states initialized from server props (No useEffect state-setting!)
  const [queueStats, setQueueStats] = useState<QueueStats | null>(initialQueue);
  const [pendingVersions, setPendingVersions] = useState<RegulationVersionAdmin[]>(initialVersions);
  const [sources, setSources] = useState<RegulationSourceAdmin[]>(initialSources);
  const [tickets, setTickets] = useState<SupportTicketAdmin[]>(initialTickets);
  const [users, setUsers] = useState<AdminUserItem[]>(initialUsers);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // News form state
  const [newsTitle, setNewsTitle] = useState('');
  const [newsContent, setNewsContent] = useState('');
  const [newsSector, setNewsSector] = useState('Logistics & Freight');
  const [newsJurisdiction, setNewsJurisdiction] = useState('Bangladesh');
  const [newsUrl, setNewsUrl] = useState('');

  // Users: create form state
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newFullName, setNewFullName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('owner');
  const [newPlan, setNewPlan] = useState('free');
  const [newIsAdmin, setNewIsAdmin] = useState(false);

  // Users: reset password modal
  const [resetUserId, setResetUserId] = useState<string | null>(null);
  const [resetPwd, setResetPwd] = useState('');

  // Users: change plan modal
  const [planUserId, setPlanUserId] = useState<string | null>(null);
  const [planValue, setPlanValue] = useState('');

  const notify = (msg: string) => {
    setSuccessMsg(msg);
    setErrorMsg(null);
  };
  const notifyErr = (msg: string) => {
    setErrorMsg(msg);
    setSuccessMsg(null);
  };

  const refreshAll = async () => {
    setErrorMsg(null);
    try {
      const [q, v, s, t, u] = await Promise.all([
        getAdminQueue().catch(() => null),
        getAdminPendingRegulations().catch(() => ({ versions: [] })),
        getAdminSources().catch(() => []),
        getAdminTickets().catch(() => []),
        getAdminUsers().catch(() => ({ users: [], total: 0 })),
      ]);
      setQueueStats(q);
      setPendingVersions(v?.versions || []);
      setSources(s || []);
      setTickets(t || []);
      setUsers(u?.users || []);
    } catch (err: unknown) {
      notifyErr(err instanceof Error ? err.message : 'Failed to refresh admin telemetry.');
    }
  };

  const handlePublish = (versionId: string) => {
    startTransition(async () => {
      try {
        await publishAdminRegulationVersion(versionId);
        notify('Regulation version published and subscriber alert fan-out enqueued.');
        await refreshAll();
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Publish failed.');
      }
    });
  };

  const handleReject = (versionId: string) => {
    startTransition(async () => {
      try {
        await rejectAdminRegulationVersion(versionId);
        notify('Regulation version rejected.');
        await refreshAll();
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Rejection failed.');
      }
    });
  };

  const handlePollSource = (sourceId: string) => {
    startTransition(async () => {
      try {
        await triggerSourcePoll(sourceId);
        notify('Source check job enqueued in worker queue.');
        await refreshAll();
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Failed to trigger poll.');
      }
    });
  };

  const handleCreateNews = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        await createAdminNews({
          title: newsTitle,
          content: newsContent,
          sector: newsSector,
          jurisdiction: newsJurisdiction,
          source_url: newsUrl || undefined,
        });
        notify('Regulatory news bulletin published successfully.');
        setNewsTitle('');
        setNewsContent('');
        setNewsUrl('');
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Failed to publish news.');
      }
    });
  };

  const handleUpdateTicketStatus = (ticketId: string, newStatus: string) => {
    startTransition(async () => {
      try {
        await updateAdminTicket(ticketId, newStatus);
        setTickets((prev) =>
          prev.map((t) => (t.id === ticketId ? { ...t, status: newStatus as 'open' | 'in_progress' | 'resolved' | 'closed' } : t))
        );
        notify(`Ticket status updated to ${newStatus}.`);
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Ticket update failed.');
      }
    });
  };

  // ── Users handlers ──────────────────────────────────────────────────────────

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      try {
        await createAdminUser({
          email: newEmail,
          password: newPassword,
          full_name: newFullName || undefined,
          role: newRole,
          plan_id: newPlan,
          is_platform_admin: newIsAdmin,
        });
        notify(`User ${newEmail} created successfully.`);
        setNewEmail(''); setNewFullName(''); setNewPassword('');
        setNewRole('owner'); setNewPlan('free'); setNewIsAdmin(false);
        setShowCreateUser(false);
        const u = await getAdminUsers();
        setUsers(u.users);
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Failed to create user.');
      }
    });
  };

  const handleResetPassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetUserId) return;
    startTransition(async () => {
      try {
        await resetAdminUserPassword(resetUserId, resetPwd);
        notify('Password reset successfully.');
        setResetUserId(null);
        setResetPwd('');
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Password reset failed.');
      }
    });
  };

  const handleChangePlan = (e: React.FormEvent) => {
    e.preventDefault();
    if (!planUserId) return;
    startTransition(async () => {
      try {
        await updateAdminUser(planUserId, { plan_id: planValue });
        notify(`Plan updated to ${planValue}.`);
        setPlanUserId(null);
        const u = await getAdminUsers();
        setUsers(u.users);
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Plan update failed.');
      }
    });
  };

  const handleToggleAdmin = (user: AdminUserItem) => {
    startTransition(async () => {
      const isAdmin = Boolean(user.is_platform_admin);
      try {
        await updateAdminUser(user.id, { is_platform_admin: !isAdmin });
        notify(`${user.email} ${isAdmin ? 'removed from' : 'promoted to'} platform admin.`);
        const u = await getAdminUsers();
        setUsers(u.users);
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Admin toggle failed.');
      }
    });
  };

  const handleDeleteUser = (user: AdminUserItem) => {
    if (!confirm(`Permanently delete ${user.email}? This cannot be undone.`)) return;
    startTransition(async () => {
      try {
        await deleteAdminUser(user.id);
        notify(`User ${user.email} deleted.`);
        setUsers((prev) => prev.filter((u) => u.id !== user.id));
      } catch (err: unknown) {
        notifyErr(err instanceof Error ? err.message : 'Delete failed.');
      }
    });
  };

  const TABS: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { key: 'queue', label: 'Worker Queue', icon: Activity },
    { key: 'regulations', label: `Pending Reviews (${pendingVersions.length})`, icon: Layers },
    { key: 'sources', label: `Sources (${sources.length})`, icon: Clock },
    { key: 'news', label: 'Curate News', icon: Newspaper },
    { key: 'tickets', label: `Support Tickets (${tickets.length})`, icon: Ticket },
    { key: 'users', label: `Users (${users.length})`, icon: Users },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-xs font-semibold mb-2 border border-indigo-200">
            <Shield className="w-3.5 h-3.5" />
            <span>Platform Operations &amp; SRO Governance</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Admin Console</h1>
          <p className="text-sm text-slate-600 mt-1">
            Supervise background worker jobs, publish detected statutory changes, poll sources, manage users, and triage customer support tickets.
          </p>
        </div>

        <button
          type="button"
          onClick={refreshAll}
          disabled={isPending}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isPending ? 'animate-spin' : ''}`} />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* Notifications banner */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-600 font-bold">×</button>
        </div>
      )}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-600 font-bold">×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap border-b border-slate-200 gap-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
                active
                  ? 'border-indigo-600 text-indigo-700 bg-indigo-50/30'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab: Queue Stats */}
      {tab === 'queue' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <span className="text-xs font-medium text-slate-500">Pending Jobs</span>
              <p className="text-2xl font-black text-slate-900 mt-1">{queueStats?.pending_count ?? 0}</p>
            </div>
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <span className="text-xs font-medium text-amber-600">Running (Leased)</span>
              <p className="text-2xl font-black text-amber-600 mt-1">{queueStats?.running_count ?? 0}</p>
            </div>
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <span className="text-xs font-medium text-emerald-600">Completed</span>
              <p className="text-2xl font-black text-emerald-600 mt-1">{queueStats?.completed_count ?? 0}</p>
            </div>
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <span className="text-xs font-medium text-slate-500">Failed (Retrying)</span>
              <p className="text-2xl font-black text-slate-700 mt-1">{queueStats?.failed_count ?? 0}</p>
            </div>
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
              <span className="text-xs font-medium text-rose-600">Dead Letters</span>
              <p className="text-2xl font-black text-rose-600 mt-1">{queueStats?.dead_letter_count ?? 0}</p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900">Active Job Leases &amp; Timestamps</h3>
            {queueStats?.running_leases && queueStats.running_leases.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-slate-100">
                      <th className="pb-2 font-semibold text-slate-500">Job ID</th>
                      <th className="pb-2 font-semibold text-slate-500">Type</th>
                      <th className="pb-2 font-semibold text-slate-500">Run At</th>
                      <th className="pb-2 font-semibold text-slate-500">Lease Until</th>
                      <th className="pb-2 font-semibold text-slate-500">Attempts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {queueStats.running_leases.map((lease) => (
                      <tr key={lease.id} className="border-b border-slate-50">
                        <td className="py-1.5 font-mono text-slate-700">{lease.id.slice(0, 12)}…</td>
                        <td className="py-1.5 text-slate-600">{lease.type}</td>
                        <td className="py-1.5 text-slate-500">{new Date(lease.run_at).toLocaleTimeString()}</td>
                        <td className="py-1.5 text-slate-500">{new Date(lease.lease_until).toLocaleTimeString()}</td>
                        <td className="py-1.5 text-slate-500">{lease.attempts}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No active job leases.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab: Pending Regulation Reviews */}
      {tab === 'regulations' && (
        <div className="space-y-4">
          {pendingVersions.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-300">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-800">All Caught Up</p>
              <p className="text-xs text-slate-500 mt-1">No regulation versions pending editorial review.</p>
            </div>
          ) : (
            pendingVersions.map((v) => (
              <div key={v.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-bold text-slate-900 mt-0.5">{v.regulation_title ?? 'Untitled Regulation'}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Version: {v.version_label} · Added: {new Date(v.created_at).toLocaleString()}</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handlePublish(v.id)}
                      disabled={isPending}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
                    >
                      Publish
                    </button>
                    <button
                      onClick={() => handleReject(v.id)}
                      disabled={isPending}
                      className="px-3 py-1.5 rounded-lg bg-rose-100 hover:bg-rose-200 text-rose-700 text-xs font-bold"
                    >
                      Reject
                    </button>
                  </div>
                </div>
                <p className="text-xs text-slate-700 bg-slate-50 p-3 rounded-xl border border-slate-100 line-clamp-4">
                  {v.text ? v.text.slice(0, 400) : 'No text preview available.'}
                </p>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab: Sources */}
      {tab === 'sources' && (
        <div className="space-y-4">
          {sources.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-300">
              <Clock className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-800">No Monitored Sources</p>
              <p className="text-xs text-slate-500 mt-1">Add regulation sources to begin automated monitoring.</p>
            </div>
          ) : (
            sources.map((s) => (
              <div key={s.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-bold text-slate-900">{s.name}</p>
                  <p className="text-xs font-mono text-slate-500">{s.url}</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${s.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                      {s.enabled ? 'Active' : 'Paused'}
                    </span>
                    {s.last_checked && (
                      <span className="text-[10px] text-slate-400">Last checked: {new Date(s.last_checked).toLocaleString()}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handlePollSource(s.id)}
                  disabled={isPending}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shrink-0"
                >
                  Poll Now
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab: Curate News */}
      {tab === 'news' && (
        <form onSubmit={handleCreateNews} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5">
          <h3 className="text-sm font-bold text-slate-900">Publish Regulatory News Bulletin</h3>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Title</label>
            <input
              type="text"
              required
              value={newsTitle}
              onChange={(e) => setNewsTitle(e.target.value)}
              placeholder="New VAT Regulation for E-commerce"
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Content</label>
            <textarea
              required
              rows={5}
              value={newsContent}
              onChange={(e) => setNewsContent(e.target.value)}
              placeholder="Summarize the regulation change and its impact..."
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Sector</label>
              <select
                value={newsSector}
                onChange={(e) => setNewsSector(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300"
              >
                <option value="Logistics & Freight">Logistics &amp; Freight</option>
                <option value="E-commerce">E-commerce</option>
                <option value="Manufacturing & Trade">Manufacturing &amp; Trade</option>
                <option value="Financial Services">Financial Services</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Jurisdiction</label>
              <input
                type="text"
                value={newsJurisdiction}
                onChange={(e) => setNewsJurisdiction(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Official Document URL</label>
            <input
              type="url"
              value={newsUrl}
              onChange={(e) => setNewsUrl(e.target.value)}
              placeholder="https://nbr.gov.bd/sro/..."
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300"
            />
          </div>
          <button
            type="submit"
            disabled={isPending}
            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-xs"
          >
            Publish Bulletin
          </button>
        </form>
      )}

      {/* Tab: Support Tickets */}
      {tab === 'tickets' && (
        <div className="space-y-4">
          {tickets.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-300">
              <Ticket className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-800">No Support Tickets Pending</p>
              <p className="text-xs text-slate-500 mt-1">All customer compliance tickets have been resolved.</p>
            </div>
          ) : (
            tickets.map((t) => (
              <div
                key={t.id}
                className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${
                        t.priority === 'urgent'
                          ? 'bg-rose-100 text-rose-700 border border-rose-300'
                          : t.priority === 'priority'
                          ? 'bg-amber-100 text-amber-700 border border-amber-300'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {t.priority}
                    </span>
                    <h4 className="text-sm font-bold text-slate-900">{t.subject}</h4>
                  </div>
                  <p className="text-xs text-slate-600">{t.message}</p>
                  <p className="text-[11px] text-slate-400">
                    From: {t.user_email} • Workspace: {t.workspace_name} • {new Date(t.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <select
                    value={t.status}
                    onChange={(e) => handleUpdateTicketStatus(t.id, e.target.value)}
                    className="px-2.5 py-1.5 text-xs rounded-xl border border-slate-300 font-semibold"
                  >
                    <option value="open">Open</option>
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </select>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab: Users */}
      {tab === 'users' && (
        <div className="space-y-6">
          {/* Create user button */}
          <div className="flex justify-between items-center">
            <p className="text-xs text-slate-500">{users.length} users registered on the platform.</p>
            <button
              onClick={() => setShowCreateUser((v) => !v)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-xs"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              {showCreateUser ? 'Cancel' : 'Create User'}
            </button>
          </div>

          {/* Create user form */}
          {showCreateUser && (
            <form onSubmit={handleCreateUser} className="bg-white p-6 rounded-2xl border border-indigo-200 shadow-xs space-y-4">
              <h3 className="text-sm font-bold text-slate-900">New Platform User</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Email *</label>
                  <input required type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300" placeholder="user@example.com" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
                  <input type="text" value={newFullName} onChange={(e) => setNewFullName(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300" placeholder="Jane Doe" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Password *</label>
                  <input required type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300" placeholder="Min 8 chars, 1 uppercase, 1 number" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Role</label>
                  <select value={newRole} onChange={(e) => setNewRole(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300">
                    {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Plan</label>
                  <select value={newPlan} onChange={(e) => setNewPlan(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300">
                    {PLAN_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div className="flex items-center gap-2 mt-5">
                  <input type="checkbox" id="newIsAdmin" checked={newIsAdmin} onChange={(e) => setNewIsAdmin(e.target.checked)}
                    className="w-4 h-4 rounded" />
                  <label htmlFor="newIsAdmin" className="text-xs font-semibold text-slate-700">Platform Admin</label>
                </div>
              </div>
              <button type="submit" disabled={isPending}
                className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold">
                Create User
              </button>
            </form>
          )}

          {/* Reset password modal */}
          {resetUserId && (
            <form onSubmit={handleResetPassword} className="bg-white p-5 rounded-2xl border border-amber-200 shadow-xs space-y-3">
              <h3 className="text-sm font-bold text-slate-900">Reset Password</h3>
              <p className="text-xs text-slate-500">Setting new password for user ID: <span className="font-mono">{resetUserId.slice(0, 12)}…</span></p>
              <input required type="password" value={resetPwd} onChange={(e) => setResetPwd(e.target.value)}
                placeholder="New password (min 8 chars, 1 uppercase, 1 number)"
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300" />
              <div className="flex gap-2">
                <button type="submit" disabled={isPending}
                  className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-white text-xs font-bold">
                  Reset Password
                </button>
                <button type="button" onClick={() => { setResetUserId(null); setResetPwd(''); }}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold">
                  Cancel
                </button>
              </div>
            </form>
          )}

          {/* Change plan modal */}
          {planUserId && (
            <form onSubmit={handleChangePlan} className="bg-white p-5 rounded-2xl border border-indigo-200 shadow-xs space-y-3">
              <h3 className="text-sm font-bold text-slate-900">Change Plan</h3>
              <select value={planValue} onChange={(e) => setPlanValue(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300">
                {PLAN_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <div className="flex gap-2">
                <button type="submit" disabled={isPending}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold">
                  Save Plan
                </button>
                <button type="button" onClick={() => setPlanUserId(null)}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold">
                  Cancel
                </button>
              </div>
            </form>
          )}

          {/* Users table */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-100">
                <tr>
                  <th className="px-4 py-3 font-semibold text-slate-500">Email</th>
                  <th className="px-4 py-3 font-semibold text-slate-500">Name</th>
                  <th className="px-4 py-3 font-semibold text-slate-500">Role</th>
                  <th className="px-4 py-3 font-semibold text-slate-500">Plan</th>
                  <th className="px-4 py-3 font-semibold text-slate-500">Admin</th>
                  <th className="px-4 py-3 font-semibold text-slate-500">Joined</th>
                  <th className="px-4 py-3 font-semibold text-slate-500 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 font-mono text-slate-700">{u.email}</td>
                    <td className="px-4 py-3 text-slate-700">{u.full_name ?? <span className="text-slate-400 italic">—</span>}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-semibold capitalize">{u.role ?? '—'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold capitalize ${
                        u.plan_id === 'professional' ? 'bg-indigo-100 text-indigo-700'
                        : u.plan_id === 'growth' ? 'bg-violet-100 text-violet-700'
                        : u.plan_id === 'starter' ? 'bg-sky-100 text-sky-700'
                        : 'bg-slate-100 text-slate-500'
                      }`}>
                        {u.plan_id ?? 'free'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {Boolean(u.is_platform_admin) ? (
                        <span title="Platform Admin"><Crown className="w-4 h-4 text-amber-500" /></span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          title="Reset Password"
                          onClick={() => { setResetUserId(u.id); setResetPwd(''); setPlanUserId(null); }}
                          className="p-1.5 rounded-lg hover:bg-amber-100 text-amber-600 transition-colors"
                        >
                          <KeyRound className="w-3.5 h-3.5" />
                        </button>
                        <button
                          title="Change Plan"
                          onClick={() => { setPlanUserId(u.id); setPlanValue(u.plan_id ?? 'free'); setResetUserId(null); }}
                          className="p-1.5 rounded-lg hover:bg-indigo-100 text-indigo-600 transition-colors"
                        >
                          <UserCog className="w-3.5 h-3.5" />
                        </button>
                        <button
                          title={Boolean(u.is_platform_admin) ? 'Remove Admin' : 'Make Admin'}
                          onClick={() => handleToggleAdmin(u)}
                          disabled={isPending}
                          className="p-1.5 rounded-lg hover:bg-amber-100 text-amber-500 transition-colors"
                        >
                          <Crown className="w-3.5 h-3.5" />
                        </button>
                        <button
                          title="Delete User"
                          onClick={() => handleDeleteUser(u)}
                          disabled={isPending}
                          className="p-1.5 rounded-lg hover:bg-rose-100 text-rose-500 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {users.length === 0 && (
              <div className="text-center py-12">
                <Users className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <p className="text-xs text-slate-500">No users found.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
