'use client';

import React from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  ShieldCheck,
  Building2,
  Layers,
  Activity,
  Globe,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
  Settings,
} from 'lucide-react';
import { LawCoverageResponse } from '@/lib/types';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

interface CoverageClientProps {
  coverage: LawCoverageResponse | null;
  isPlatformAdmin: boolean;
}

export function CoverageClient({ coverage, isPlatformAdmin }: CoverageClientProps) {
  const sources = coverage?.sources || [];
  const runs = coverage?.recent_runs || [];
  const byType = coverage?.by_law_type || {};
  const byBody = coverage?.by_issuing_body || {};

  return (
    <div className="space-y-8 py-4">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/laws"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Legal Library</span>
        </Link>

        {isPlatformAdmin && (
          <Link
            href="/admin/laws"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 hover:bg-purple-100 text-xs font-semibold transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Admin Review Queue & Sources</span>
          </Link>
        )}
      </div>

      {/* Hero / Coverage Methodology Notice */}
      <div className="p-6 sm:p-8 rounded-3xl bg-slate-900 text-white space-y-4 shadow-sm">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Real-Time Ingestion & Coverage Telemetry</span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
          Bangladesh Regulatory Coverage Dashboard
        </h1>

        <div className="p-4 rounded-2xl bg-slate-800/80 border border-slate-700/80 text-xs text-slate-300 leading-relaxed space-y-2">
          <p className="font-semibold text-white">
            Transparency Notice: Zero Claims of Completeness
          </p>
          <p>
            ComplianceOS does not crawl or store every Bangladesh law. Coverage reflects active discovery pipelines from configured government sources (e.g. Bangladesh Government Press, Ministry of Law legislative portal, NBR, and Bangladesh Bank). New enactments, SROs, and circulars are ingested, diffed, and critic-verified systematically.
          </p>
        </div>
      </div>

      {/* Top Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-1.5">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-semibold">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>Published Enactments</span>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold font-mono text-slate-900">
            {coverage?.published_laws_count ?? 0}
          </p>
          <p className="text-[11px] text-slate-500">Live in search & RAG pipeline</p>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-1.5">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-semibold">
            <Clock className="w-4 h-4 text-amber-600" />
            <span>Pending Review</span>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold font-mono text-slate-900">
            {coverage?.pending_review_count ?? 0}
          </p>
          <p className="text-[11px] text-slate-500">Queued for critic verification</p>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-1.5">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-semibold">
            <Globe className="w-4 h-4 text-indigo-600" />
            <span>Monitored Sources</span>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold font-mono text-slate-900">
            {coverage?.enabled_sources_count ?? 0}
            <span className="text-base text-slate-400 font-normal"> / {coverage?.total_sources_count ?? 0}</span>
          </p>
          <p className="text-[11px] text-slate-500">Configured official portals</p>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-1.5">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-semibold">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            <span>Failed / Blocked Runs</span>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold font-mono text-slate-900">
            {coverage?.failed_sources_count ?? 0}
          </p>
          <p className="text-[11px] text-slate-500">Safe SSRF / rate-limit backoff</p>
        </div>
      </div>

      {/* Breakdowns by Type and Issuing Body */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* By Law Type */}
        <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-2xs space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Layers className="w-4 h-4 text-indigo-600" />
            <span>Coverage by Enactment Type</span>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {Object.keys(byType).length === 0 ? (
              <p className="text-xs text-slate-400 col-span-2">No categorized laws yet.</p>
            ) : (
              Object.entries(byType).map(([type, count]) => (
                <div
                  key={type}
                  className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between"
                >
                  <span className="text-xs font-medium text-slate-700 capitalize">
                    {type.replace('_', ' ')}
                  </span>
                  <span className="font-mono text-xs font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {count}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* By Issuing Body */}
        <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-2xs space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Building2 className="w-4 h-4 text-emerald-600" />
            <span>Coverage by Issuing Government Body</span>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {Object.keys(byBody).length === 0 ? (
              <p className="text-xs text-slate-400 col-span-2">No issuing bodies recorded yet.</p>
            ) : (
              Object.entries(byBody).map(([body, count]) => (
                <div
                  key={body}
                  className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between"
                >
                  <span className="text-xs font-medium text-slate-700 truncate pr-2">
                    {body}
                  </span>
                  <span className="font-mono text-xs font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200 shrink-0">
                    {count}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Monitored Government Portals Table */}
      <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Globe className="w-4 h-4 text-indigo-600" />
            <span>Monitored Government Feeds & Portals</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-100 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="pb-3 pr-4">Source Name</th>
                <th className="pb-3 px-4">Base URL</th>
                <th className="pb-3 px-4">Type</th>
                <th className="pb-3 px-4">Rate Limit</th>
                <th className="pb-3 px-4">Status</th>
                <th className="pb-3 pl-4">Last Run</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sources.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-400">
                    No law sources configured.
                  </td>
                </tr>
              ) : (
                sources.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 pr-4 font-semibold text-slate-900">
                      {s.name}
                    </td>
                    <td className="py-3 px-4">
                      <a
                        href={s.base_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-800 flex items-center gap-1 max-w-[200px] truncate"
                      >
                        <span className="truncate">{s.base_url}</span>
                        <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-600">
                      {s.source_type}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {s.rate_limit}s delay
                    </td>
                    <td className="py-3 px-4">
                      {s.enabled ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                          Active Crawl
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-medium border border-slate-200">
                          Disabled
                        </span>
                      )}
                    </td>
                    <td className="py-3 pl-4 font-mono text-[11px] text-slate-500">
                      {s.last_run_at ? s.last_run_at.slice(0, 16).replace('T', ' ') : 'Never'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Ingestion Runs Table */}
      {runs.length > 0 && (
        <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-2xs space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Activity className="w-4 h-4 text-emerald-600" />
            <span>Recent Ingestion & Change Detection Runs</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-100 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="pb-3 pr-4">Run Started</th>
                  <th className="pb-3 px-4">Discovered</th>
                  <th className="pb-3 px-4">New Laws</th>
                  <th className="pb-3 px-4">Amendments Detected</th>
                  <th className="pb-3 px-4">Failed</th>
                  <th className="pb-3 pl-4">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 pr-4 font-mono text-slate-700">
                      {r.started_at.slice(0, 16).replace('T', ' ')}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-700">{r.discovered}</td>
                    <td className="py-3 px-4 font-mono font-bold text-emerald-600">+{r.new}</td>
                    <td className="py-3 px-4 font-mono font-bold text-amber-600">~{r.changed}</td>
                    <td className="py-3 px-4 font-mono text-rose-600">{r.failed}</td>
                    <td className="py-3 pl-4 text-slate-500 max-w-[250px] truncate">{r.notes || 'Routine run'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Mandatory Legal Disclaimer */}
      <LegalDisclaimer />
    </div>
  );
}
