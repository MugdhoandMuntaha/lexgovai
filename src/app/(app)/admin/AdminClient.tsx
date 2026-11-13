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
} from '@/lib/api';
import {
  QueueStats,
  RegulationSourceAdmin,
  RegulationVersionAdmin,
  SupportTicketAdmin,
} from '@/lib/types';

interface Props {
  initialQueue: QueueStats | null;
  initialVersions: RegulationVersionAdmin[];
  initialSources: RegulationSourceAdmin[];
  initialTickets: SupportTicketAdmin[];
}

export function AdminClient({
  initialQueue,
  initialVersions,
  initialSources,
  initialTickets,
}: Props) {
  const [tab, setTab] = useState<'queue' | 'regulations' | 'sources' | 'news' | 'tickets'>('queue');
  const [isPending, startTransition] = useTransition();

  // Data states initialized from server props (No useEffect state-setting!)
  const [queueStats, setQueueStats] = useState<QueueStats | null>(initialQueue);
  const [pendingVersions, setPendingVersions] = useState<RegulationVersionAdmin[]>(initialVersions);
  const [sources, setSources] = useState<RegulationSourceAdmin[]>(initialSources);
  const [tickets, setTickets] = useState<SupportTicketAdmin[]>(initialTickets);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // News form state
  const [newsTitle, setNewsTitle] = useState('');
  const [newsContent, setNewsContent] = useState('');
  const [newsSector, setNewsSector] = useState('Logistics & Freight');
  const [newsJurisdiction, setNewsJurisdiction] = useState('Bangladesh');
  const [newsUrl, setNewsUrl] = useState('');

  const refreshAll = async () => {
    setErrorMsg(null);
    try {
      const [q, v, s, t] = await Promise.all([
        getAdminQueue().catch(() => null),
        getAdminPendingRegulations().catch(() => ({ versions: [] })),
        getAdminSources().catch(() => []),
        getAdminTickets().catch(() => []),
      ]);
      setQueueStats(q);
      setPendingVersions(v?.versions || []);
      setSources(s || []);
      setTickets(t || []);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to refresh admin telemetry.');
    }
  };

  const handlePublish = (versionId: string) => {
    startTransition(async () => {
      try {
        await publishAdminRegulationVersion(versionId);
        setSuccessMsg('Regulation version published and subscriber alert fan-out enqueued.');
        await refreshAll();
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Publish failed.');
      }
    });
  };

  const handleReject = (versionId: string) => {
    startTransition(async () => {
      try {
        await rejectAdminRegulationVersion(versionId);
        setSuccessMsg('Regulation version rejected.');
        await refreshAll();
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Rejection failed.');
      }
    });
  };

  const handlePollSource = (sourceId: string) => {
    startTransition(async () => {
      try {
        await triggerSourcePoll(sourceId);
        setSuccessMsg('Source check job enqueued in worker queue.');
        await refreshAll();
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to trigger poll.');
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
        setSuccessMsg('Regulatory news bulletin published successfully.');
        setNewsTitle('');
        setNewsContent('');
        setNewsUrl('');
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to publish news.');
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
        setSuccessMsg(`Ticket status updated to ${newStatus}.`);
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Ticket update failed.');
      }
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-xs font-semibold mb-2 border border-indigo-200">
            <Shield className="w-3.5 h-3.5" />
            <span>Platform Operations & SRO Governance</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Admin Console</h1>
          <p className="text-sm text-slate-600 mt-1">
            Supervise background worker jobs, publish detected statutory changes, poll sources, and triage customer support tickets.
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
      <div className="flex border-b border-slate-200 gap-2">
        {[
          { key: 'queue', label: 'Worker Queue', icon: Activity },
          { key: 'regulations', label: `Pending Reviews (${pendingVersions.length})`, icon: Layers },
          { key: 'sources', label: `Sources (${sources.length})`, icon: Clock },
          { key: 'news', label: 'Curate News', icon: Newspaper },
          { key: 'tickets', label: `Support Tickets (${tickets.length})`, icon: Ticket },
        ].map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key as typeof tab)}
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
            <h3 className="text-sm font-bold text-slate-900">Active Job Leases & Timestamps</h3>
            {queueStats?.running_leases && queueStats.running_leases.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-slate-100 text-slate-400 font-medium">
                      <th className="py-2">Job Type</th>
                      <th className="py-2">Lease Expires At</th>
                      <th className="py-2">Attempts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {queueStats.running_leases.map((l) => (
                      <tr key={l.id} className="border-b border-slate-50">
                        <td className="py-2 font-mono font-semibold text-slate-800">{l.type}</td>
                        <td className="py-2 text-slate-500">{l.lease_until}</td>
                        <td className="py-2 text-slate-600">{l.attempts}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-500">No background jobs currently running leases.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab: Regulations Pending Review */}
      {tab === 'regulations' && (
        <div className="space-y-4">
          {pendingVersions.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-300">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-800">All Regulation Versions Published</p>
              <p className="text-xs text-slate-500 mt-1">
                No pending diffs or crawler candidates waiting for legal review.
              </p>
            </div>
          ) : (
            pendingVersions.map((v) => (
              <div
                key={v.id}
                className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">{v.regulation_title}</h3>
                    <p className="text-xs text-slate-500 font-mono">
                      Version: {v.version_label} • Status: {v.status}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handlePublish(v.id)}
                      disabled={isPending}
                      className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all shadow-xs"
                    >
                      Publish & Fan-Out Alerts
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReject(v.id)}
                      disabled={isPending}
                      className="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 text-xs font-semibold"
                    >
                      Reject
                    </button>
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs text-slate-700 max-h-48 overflow-y-auto">
                  <pre className="whitespace-pre-wrap">{v.text}</pre>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab: Sources */}
      {tab === 'sources' && (
        <div className="space-y-4">
          <div className="grid gap-4">
            {sources.map((s) => (
              <div
                key={s.id}
                className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-slate-900">{s.name}</h4>
                    <span
                      className={`px-2 py-0.5 rounded-md text-[10px] font-semibold ${
                        s.enabled ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {s.enabled ? 'Active Poller' : 'Disabled'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 font-mono mt-1">{s.url || 'Manual Feed'}</p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Last checked: {s.last_checked ? new Date(s.last_checked).toLocaleString() : 'Never'}
                    {s.last_error && ` • Error: ${s.last_error}`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handlePollSource(s.id)}
                  disabled={isPending}
                  className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shrink-0"
                >
                  Poll Now
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Curate News */}
      {tab === 'news' && (
        <form onSubmit={handleCreateNews} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4 max-w-2xl">
          <h3 className="text-base font-bold text-slate-900">Publish Regulatory News Item</h3>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Headline</label>
            <input
              type="text"
              required
              value={newsTitle}
              onChange={(e) => setNewsTitle(e.target.value)}
              placeholder="e.g. NBR Issues SRO 182 Regarding Electronic Filing"
              className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Content / Summary</label>
            <textarea
              required
              rows={4}
              value={newsContent}
              onChange={(e) => setNewsContent(e.target.value)}
              placeholder="Detailed statutory directive or gazette announcement..."
              className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Sector</label>
              <select
                value={newsSector}
                onChange={(e) => setNewsSector(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300"
              >
                <option value="Logistics & Freight">Logistics & Freight</option>
                <option value="E-commerce">E-commerce</option>
                <option value="Manufacturing & Trade">Manufacturing & Trade</option>
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
    </div>
  );
}
