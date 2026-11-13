'use client';

import React, { useState, useTransition } from 'react';
import Link from 'next/link';
import {
  LifeBuoy,
  Send,
  Clock,
  CheckCircle,
  AlertCircle,
  Sparkles,
  HelpCircle,
} from 'lucide-react';
import { SupportTicketItem } from '@/lib/types';
import { createSupportTicket } from '@/lib/api';

interface SupportClientProps {
  initialTickets: SupportTicketItem[];
  userPlanId: string;
  userName: string;
  userEmail: string;
}

export function SupportClient({
  initialTickets,
  userPlanId,
  userEmail,
}: SupportClientProps) {
  const [tickets, setTickets] = useState<SupportTicketItem[]>(initialTickets);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedTicketId, setExpandedTicketId] = useState<string | null>(null);

  const [isPending, startTransition] = useTransition();

  const isProfessional = userPlanId === 'professional';
  const isGrowth = userPlanId === 'growth';

  const slaTitle = isProfessional
    ? '4-Hour Dedicated Engineering Response'
    : isGrowth
    ? '12-Hour Priority Support Desk'
    : '48-Hour Standard Compliance Support';

  const slaBadgeColor = isProfessional
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : isGrowth
    ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
    : 'bg-slate-100 text-slate-700 border-slate-200';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) return;
    setErrorMsg(null);
    setSuccessNotice(null);

    startTransition(async () => {
      try {
        const res = await createSupportTicket(subject.trim(), message.trim());
        setTickets((prev) => [res.ticket, ...prev]);
        setSuccessNotice(`Ticket #${res.ticket.id.slice(0, 8)} submitted successfully. SLA: ${res.sla}.`);
        setSubject('');
        setMessage('');
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to submit support ticket.');
      }
    });
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="flex items-center gap-2 text-indigo-600 font-semibold text-xs tracking-wider uppercase mb-1">
            <LifeBuoy className="w-4 h-4" />
            <span>Customer Desk</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Support & Help Desk</h1>
          <p className="text-sm text-slate-600 mt-1">
            Submit regulatory inquiries, technical bug reports, or request expert assistance from our legal team.
          </p>
        </div>

        <div className={`px-3.5 py-1.5 rounded-full border text-xs font-semibold flex items-center gap-2 ${slaBadgeColor}`}>
          <Clock className="w-3.5 h-3.5" />
          <span>{slaTitle}</span>
        </div>
      </div>

      {/* SLA Info Banner */}
      {!isProfessional && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-50/70 via-sky-50/70 to-slate-50 border border-indigo-100 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-xs font-bold text-slate-900">Need expedited turnaround?</h2>
              <p className="text-[11px] text-slate-600">
                Professional tier subscribers receive dedicated 4-hour SLA routing with direct compliance engineer assignment.
              </p>
            </div>
          </div>
          <Link
            href="/pricing"
            className="px-3 py-1.5 rounded-xl bg-slate-900 text-white font-semibold text-xs shrink-0 hover:bg-slate-800 transition-all shadow-xs"
          >
            Upgrade Plan
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Ticket Form */}
        <div className="lg:col-span-3 p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-5">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Send className="w-4 h-4 text-indigo-600" />
            <span>Submit a New Ticket</span>
          </h2>

          {successNotice && (
            <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>{successNotice}</span>
            </div>
          )}

          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Subject
              </label>
              <input
                type="text"
                required
                minLength={3}
                placeholder="e.g. Question regarding NBR SRO 4.2 VAT withholding"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Message & Details
              </label>
              <textarea
                required
                minLength={10}
                rows={5}
                placeholder="Describe your issue or regulatory inquiry in detail. Include relevant clause numbers or SOP section names if applicable."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-500">
                Replying to: <strong className="text-slate-700">{userEmail}</strong>
              </span>

              <button
                type="submit"
                disabled={isPending || !subject.trim() || !message.trim()}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-xs transition-all disabled:opacity-50"
              >
                {isPending ? 'Submitting...' : 'Submit Ticket'}
              </button>
            </div>
          </form>
        </div>

        {/* Sidebar Info */}
        <div className="lg:col-span-2 space-y-4">
          <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
              <HelpCircle className="w-3.5 h-3.5 text-indigo-600" />
              <span>Support Guidelines</span>
            </h3>
            <ul className="text-xs text-slate-600 space-y-2 list-disc list-inside">
              <li>General questions regarding VAT and Companies Act are typically answered within your plan SLA window.</li>
              <li>Our team cannot execute legally binding filings on your behalf, but will clarify statutory clauses and SRO applicability.</li>
              <li>Emergency notifications regarding audit deadlines are automatically flagged to our senior compliance officers.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Ticket History */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h2 className="text-base font-bold text-slate-900">Your Tickets ({tickets.length})</h2>
          <span className="text-xs text-slate-500">Tickets are logged with transactional email receipts</span>
        </div>

        {tickets.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-400 text-xs">
            No support tickets submitted yet. Fill out the form above if you need assistance.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {tickets.map((t) => {
              const isExpanded = expandedTicketId === t.id;
              return (
                <div key={t.id} className="p-6 hover:bg-slate-50/60 transition-colors space-y-2">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => setExpandedTicketId(isExpanded ? null : t.id)}
                      className="text-left font-bold text-slate-900 hover:text-indigo-600 text-sm"
                    >
                      {t.subject}
                    </button>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase ${
                          t.priority === 'urgent'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : t.priority === 'priority'
                            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                            : 'bg-slate-100 text-slate-700 border border-slate-200'
                        }`}
                      >
                        {t.priority}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize ${
                          t.status === 'resolved'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : t.status === 'in_progress'
                            ? 'bg-sky-50 text-sky-700 border border-sky-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {t.status.replace('_', ' ')}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-slate-400 font-mono">
                    <span>ID: #{t.id.slice(0, 8)}</span>
                    <span>{new Date(t.created_at).toLocaleDateString()}</span>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 p-4 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700 whitespace-pre-wrap">
                      {t.message}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
