'use client';

import React, { useState, useTransition } from 'react';
import Link from 'next/link';
import {
  ShieldAlert,
  CheckCircle2,
  RefreshCw,
  FileDiff,
  Hash,
  Scale,
  ArrowRight,
  FileText,
} from 'lucide-react';
import {
  RegulationChangeResponse,
  RegulationDetailResponse,
  RegulationSummary,
} from '@/lib/types';
import { detectSpecificRegulationChange, getRegulationDetail } from '@/lib/api';

interface RegulationsClientProps {
  initialRegulations: RegulationSummary[];
  initialDetail: RegulationDetailResponse | null;
}

export function RegulationsClient({
  initialRegulations,
  initialDetail,
}: RegulationsClientProps) {
  const [regulations] = useState<RegulationSummary[]>(initialRegulations);
  const [selectedId, setSelectedId] = useState<string>(
    initialDetail?.regulation.id || initialRegulations[0]?.id || 'nbr-vat-sro-4.2'
  );
  const [detail, setDetail] = useState<RegulationDetailResponse | null>(initialDetail);
  const [watcherData, setWatcherData] = useState<RegulationChangeResponse | null>(null);
  const [loadingWatcher, setLoadingWatcher] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const handleSelectRegulation = (regId: string) => {
    if (regId === selectedId) return;
    setSelectedId(regId);
    setWatcherData(null);
    setError(null);
    setLoadingDetail(true);

    startTransition(async () => {
      try {
        const res = await getRegulationDetail(regId);
        setDetail(res);
      } catch (err: unknown) {
        console.error('Failed to load regulation detail', err);
        setError(err instanceof Error ? err.message : 'Failed to load regulation detail.');
      } finally {
        setLoadingDetail(false);
      }
    });
  };

  const handleRunWatcher = async () => {
    setLoadingWatcher(true);
    setError(null);
    try {
      const res = await detectSpecificRegulationChange(selectedId);
      setWatcherData(res);
    } catch (err: unknown) {
      console.error('Failed to run watcher for regulation', err);
      setError(err instanceof Error ? err.message : 'Watcher agent failed to run.');
    } finally {
      setLoadingWatcher(false);
    }
  };

  const beforeText = detail?.pair.before_text || '';
  const afterText = detail?.pair.after_text || '';
  const versionHash = watcherData?.version_hash || detail?.pair.version_hash || '';
  const changeSummary = watcherData?.change_summary || detail?.latest_change?.summary;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-700 mb-1">
            <Scale className="w-4 h-4 text-emerald-600" />
            <span>Multi-Regulation Intelligence Library</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Statutory Regulations Catalog
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Select a statutory act to inspect cryptographic amendments, extract testable obligations with Agent 1, or benchmark your SOP.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href={`/upload?regulation=${encodeURIComponent(selectedId)}`}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-xs transition-all shrink-0"
          >
            <FileText className="w-4 h-4" />
            <span>Benchmark SOP With This Law</span>
          </Link>
          <button
            type="button"
            onClick={handleRunWatcher}
            disabled={loadingWatcher || loadingDetail}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-semibold transition-all shrink-0 shadow-2xs disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-emerald-600 ${loadingWatcher ? 'animate-spin' : ''}`} />
            <span>{watcherData ? 'Re-Run Watcher' : 'Analyze Changes with Agent 1'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
          {error}
        </div>
      )}

      {/* Regulation Selector Catalog Tabs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {regulations.map((reg) => {
          const isSelected = reg.id === selectedId;
          return (
            <button
              key={reg.id}
              type="button"
              onClick={() => handleSelectRegulation(reg.id)}
              className={`text-left p-5 rounded-3xl border transition-all shadow-2xs relative ${
                isSelected
                  ? 'bg-white border-emerald-600 ring-2 ring-emerald-600/20'
                  : 'bg-white/80 border-slate-200/90 hover:bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                  {reg.sector || 'General Corporate'}
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  {reg.version_count} versions
                </span>
              </div>
              <h3 className="text-sm font-bold text-slate-900 line-clamp-1">{reg.title}</h3>
              <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                {reg.description || 'Statutory regulatory order for corporate operations.'}
              </p>
              {isSelected && (
                <div className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
                  <span>Active Statutory Benchmark</span>
                  <ArrowRight className="w-3 h-3" />
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Active Regulation Overview Card */}
      {detail && (
        <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xs">
          <div className="flex flex-wrap items-start justify-between gap-4 pb-4 border-b border-slate-100">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">Jurisdiction:</span>
                <span className="text-xs font-semibold text-slate-800">{detail.regulation.country}</span>
                <span>•</span>
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">Sector:</span>
                <span className="text-xs font-semibold text-slate-800">{detail.regulation.sector || 'All SMEs'}</span>
              </div>
              <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                {detail.regulation.title}
              </h2>
              <p className="text-xs text-slate-600 max-w-3xl leading-relaxed">
                {detail.regulation.description}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 font-semibold flex items-center gap-1">
                <Hash className="w-3.5 h-3.5 text-slate-400" />
                Hash: {versionHash.slice(0, 12)}
              </span>
            </div>
          </div>

          {/* Watcher Analysis Card (from Agent 1 or cached change) */}
          {watcherData ? (
            <div className="space-y-4 rounded-2xl bg-emerald-50/40 p-5 border border-emerald-200/80">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-emerald-600" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-900">
                    Agent 1 Watcher Output & Obligations
                  </h4>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800">
                  {watcherData.change_type}
                </span>
              </div>

              <div>
                <h5 className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Plain-Language Summary
                </h5>
                <p className="text-xs text-slate-800 leading-relaxed bg-white p-3.5 rounded-xl border border-emerald-100">
                  {watcherData.change_summary}
                </p>
              </div>

              {watcherData.changed_clauses?.length > 0 && (
                <div>
                  <h5 className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Amended Clauses
                  </h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {watcherData.changed_clauses.map((clause, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2 p-3 rounded-xl bg-white border border-emerald-100 text-xs text-slate-700"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                        <span>{clause}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {watcherData.obligations?.length > 0 && (
                <div>
                  <h5 className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Extracted Mandatory Business Obligations
                  </h5>
                  <div className="space-y-1.5">
                    {watcherData.obligations.map((obligation, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2 p-2.5 rounded-xl bg-white border border-emerald-100 text-xs text-slate-800 font-medium"
                      >
                        <span className="font-mono text-emerald-700 font-bold shrink-0">{idx + 1}.</span>
                        <span>{obligation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : changeSummary ? (
            <div className="rounded-2xl bg-slate-50 p-4 border border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                  Pre-Analyzed Regulatory Change Summary
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  {detail.latest_change?.change_type || 'Amendment'}
                </span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed">
                {changeSummary}
              </p>
            </div>
          ) : null}

          {/* Cryptographic Diff Comparison (Before vs After) */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-base font-bold text-slate-900">
                <FileDiff className="w-5 h-5 text-emerald-600" />
                <h3>Cryptographic Statutory Text Comparison</h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                SHA-256: {versionHash}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Previous Version */}
              <div className="bg-white border border-rose-200 rounded-3xl p-5 space-y-3 shadow-2xs">
                <div className="flex items-center justify-between pb-2 border-b border-rose-100">
                  <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                    {detail.pair.before_title || 'Previous Statutory Edition'}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 font-mono">
                    Before
                  </span>
                </div>
                <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200 max-h-96 overflow-y-auto">
                  {beforeText || 'No previous version text found.'}
                </pre>
              </div>

              {/* Revised Version */}
              <div className="bg-white border border-emerald-200 rounded-3xl p-5 space-y-3 shadow-2xs">
                <div className="flex items-center justify-between pb-2 border-b border-emerald-100">
                  <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
                    {detail.pair.after_title || 'Revised Statutory Edition'}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono">
                    Revised / Active
                  </span>
                </div>
                <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200 max-h-96 overflow-y-auto">
                  {afterText || 'No revised version text found.'}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
