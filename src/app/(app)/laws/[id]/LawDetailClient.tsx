'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Bell,
  Layers,
  Sparkles,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Send,
  Building2,
  FileText,
  HelpCircle,
  Copy,
  Check,
  Search,
  Scale,
  GitCompare,
} from 'lucide-react';
import { LawDetailResponse, LawSectionItem } from '@/lib/types';
import { watchLaw, unwatchLaw, askLaw, analyzeLawAgainstSOP } from '@/lib/api';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

interface LawDetailClientProps {
  detail: LawDetailResponse;
  initialSections: LawSectionItem[];
}

export function LawDetailClient({ detail, initialSections }: LawDetailClientProps) {
  const router = useRouter();
  const { law, current_version, versions, relations } = detail;

  const [isWatched, setIsWatched] = useState(detail.is_watched);
  const [isWatchLoading, setIsWatchLoading] = useState(false);
  const [showBengaliTitle, setShowBengaliTitle] = useState(false);
  const [sectionFilter, setSectionFilter] = useState('');
  const [copiedSectionId, setCopiedSectionId] = useState<string | null>(null);

  // Ask-the-law state
  const [isAskOpen, setIsAskOpen] = useState(false);
  const [askQuery, setAskQuery] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [askResult, setAskResult] = useState<{
    answer: string;
    citations: Array<{ section_number: string; snippet: string; verified: boolean }>;
  } | null>(null);
  const [askError, setAskError] = useState<string | null>(null);

  // Analyze modal state
  const [isAnalyzeModalOpen, setIsAnalyzeModalOpen] = useState(false);
  const [sopDocId, setSopDocId] = useState('');
  const [companyProfileId, setCompanyProfileId] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const handleToggleWatch = async () => {
    setIsWatchLoading(true);
    try {
      if (isWatched) {
        await unwatchLaw(law.id);
        setIsWatched(false);
      } else {
        await watchLaw(law.id);
        setIsWatched(true);
      }
    } catch (err) {
      console.error('Failed to toggle watch:', err);
    } finally {
      setIsWatchLoading(false);
    }
  };

  const handleCopyLink = (sectionId: string, numberLabel: string) => {
    const url = `${window.location.origin}/laws/${law.id}#${encodeURIComponent(numberLabel)}`;
    navigator.clipboard.writeText(url);
    setCopiedSectionId(sectionId);
    setTimeout(() => setCopiedSectionId(null), 2000);
  };

  const handleAskSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!askQuery.trim() || isAsking) return;
    setIsAsking(true);
    setAskError(null);
    try {
      const res = await askLaw(askQuery.trim(), law.id);
      setAskResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to query statutory clauses.';
      setAskError(msg);
    } finally {
      setIsAsking(false);
    }
  };

  const handleRunAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sopDocId.trim() || !companyProfileId.trim() || isAnalyzing) return;
    setIsAnalyzing(true);
    setAnalyzeError(null);
    try {
      const res = await analyzeLawAgainstSOP(law.id, companyProfileId.trim(), sopDocId.trim());
      router.push(`/action-plan/${res.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Analysis failed. Check your plan quota.';
      setAnalyzeError(msg);
      setIsAnalyzing(false);
    }
  };

  const filteredSections = initialSections.filter((sec) => {
    if (!sectionFilter.trim()) return true;
    const q = sectionFilter.toLowerCase();
    return (
      sec.number_label.toLowerCase().includes(q) ||
      (sec.heading && sec.heading.toLowerCase().includes(q)) ||
      sec.text.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-8 py-4">
      {/* Back button & Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          href="/laws"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Legal Library</span>
        </Link>

        {versions.length > 1 && (
          <Link
            href={`/laws/${law.id}/diff`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-indigo-200 bg-indigo-50/60 text-indigo-700 text-xs font-semibold hover:bg-indigo-100 transition-colors"
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Compare {versions.length} Versions</span>
          </Link>
        )}
      </div>

      {/* Main Law Header Card */}
      <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-3 flex-1 min-w-0">
            {/* Meta Tags */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                  law.status === 'in_force'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : law.status === 'amended'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : law.status === 'repealed'
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                {law.status.replace('_', ' ')}
              </span>

              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-mono font-semibold uppercase tracking-wider">
                {law.law_type.replace('_', ' ')}
              </span>

              {law.year && (
                <span className="font-mono text-slate-600 text-xs font-semibold">
                  {law.act_number ? `${law.act_number} of ` : ''}
                  {law.year}
                </span>
              )}

              <span className="text-slate-500 text-xs flex items-center gap-1 font-medium">
                <Building2 className="w-3.5 h-3.5 text-slate-400" />
                {law.issuing_body}
              </span>
            </div>

            {/* Title with Language Switch */}
            <div className="space-y-1">
              <h1 className="text-xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                {showBengaliTitle && law.canonical_title_bn ? law.canonical_title_bn : law.canonical_title_en}
              </h1>
              {law.canonical_title_bn && (
                <div className="flex items-center gap-2 pt-0.5">
                  <p className="text-xs text-slate-500 font-sans">
                    {showBengaliTitle ? law.canonical_title_en : law.canonical_title_bn}
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowBengaliTitle((prev) => !prev)}
                    className="text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold px-2 py-0.5 rounded bg-indigo-50 border border-indigo-100 transition-colors"
                  >
                    Switch to {showBengaliTitle ? 'English' : 'Bengali (বাংলা)'}
                  </button>
                </div>
              )}
            </div>

            {/* Official Source Link Warning */}
            {current_version?.source_url ? (
              <div className="pt-1 flex items-center gap-2 text-xs">
                <a
                  href={current_version.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-indigo-600 hover:text-indigo-800 font-semibold underline underline-offset-2"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Authoritative Gazette Source ({new URL(current_version.source_url).hostname})</span>
                </a>
                <span className="text-slate-400">·</span>
                <span className="text-slate-500 italic text-[11px]">
                  Official gazette text is the sole legally authoritative baseline
                </span>
              </div>
            ) : null}
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap md:flex-col gap-2 shrink-0">
            <button
              type="button"
              onClick={handleToggleWatch}
              disabled={isWatchLoading}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 border transition-all ${
                isWatched
                  ? 'bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100'
                  : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              <Bell className={`w-3.5 h-3.5 ${isWatched ? 'fill-amber-500 text-amber-500' : 'text-slate-400'}`} />
              <span>{isWatched ? 'Watching for Changes' : 'Watch this Law'}</span>
            </button>

            <button
              type="button"
              onClick={() => setIsAskOpen((prev) => !prev)}
              className="px-4 py-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-100 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              <HelpCircle className="w-3.5 h-3.5 text-indigo-600" />
              <span>Ask about this Law</span>
            </button>

            <button
              type="button"
              onClick={() => setIsAnalyzeModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-2xs"
            >
              <Scale className="w-3.5 h-3.5" />
              <span>Analyze SOP Against Law</span>
            </button>
          </div>
        </div>

        {/* AI Grounded Summary */}
        {law.summary_ai && (
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>AI-Generated Executive Summary</span>
              </div>

              {law.summary_verified ? (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[10px] font-bold text-emerald-700">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Verified Against Source Text (RapidFuzz Critic)</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-[10px] font-semibold text-amber-700">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  <span>AI Output · Critic Verification Pending</span>
                </div>
              )}
            </div>
            <p className="text-xs sm:text-sm text-slate-700 leading-relaxed">
              {law.summary_ai}
            </p>
          </div>
        )}

        {/* Relations (Amends, Repeals, Implements) */}
        {relations && relations.length > 0 && (
          <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100 space-y-2">
            <h4 className="text-xs font-bold text-indigo-900 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              <span>Statutory Relationships</span>
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              {relations.map((rel) => {
                const isTarget = rel.from_law_id === law.id;
                const otherTitle = isTarget ? rel.to_law_title : rel.from_law_title;
                const otherId = isTarget ? rel.to_law_id : rel.from_law_id;
                return (
                  <div
                    key={rel.id}
                    className="p-2.5 rounded-xl bg-white border border-indigo-200/80 flex items-center justify-between gap-2"
                  >
                    <span className="font-semibold text-indigo-900 uppercase text-[10px] px-2 py-0.5 rounded bg-indigo-50">
                      {rel.relation}
                    </span>
                    <Link
                      href={`/laws/${otherId}`}
                      className="text-slate-800 hover:text-indigo-600 font-medium truncate flex-1 text-right text-xs"
                    >
                      {otherTitle || otherId}
                    </Link>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Ask About This Law Drawer / Section */}
      {isAskOpen && (
        <div className="p-6 rounded-3xl bg-white border-2 border-indigo-200 shadow-md space-y-4 animate-in fade-in">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Ask About {law.canonical_title_en}</h3>
                <p className="text-xs text-slate-500">
                  Grounded strictly in the statutory sections below. No hallucinated legal claims.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsAskOpen(false)}
              className="text-slate-400 hover:text-slate-700 text-xs font-semibold"
            >
              Close
            </button>
          </div>

          <form onSubmit={handleAskSubmit} className="flex gap-2">
            <input
              type="text"
              value={askQuery}
              onChange={(e) => setAskQuery(e.target.value)}
              placeholder="e.g. What is the penalty for late VAT return filing under Section 85?"
              className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400"
            />
            <button
              type="submit"
              disabled={isAsking || !askQuery.trim()}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{isAsking ? 'Searching Sections...' : 'Ask'}</span>
            </button>
          </form>

          {askError && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{askError}</span>
            </div>
          )}

          {askResult && (
            <div className="p-4 rounded-2xl bg-indigo-50/40 border border-indigo-200 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-indigo-900">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Grounded Statutory Answer</span>
              </div>
              <p className="text-xs sm:text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
                {askResult.answer}
              </p>

              {askResult.citations && askResult.citations.length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-indigo-100">
                  <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                    Authoritative Citations (RapidFuzz Verified):
                  </span>
                  <div className="space-y-1">
                    {askResult.citations.map((c, i) => (
                      <div
                        key={i}
                        className="p-2 rounded-lg bg-white border border-indigo-100 text-xs flex items-start justify-between gap-2"
                      >
                        <div className="space-y-0.5">
                          <span className="font-bold text-indigo-700 font-mono text-[11px]">
                            {c.section_number}
                          </span>
                          <p className="text-[11px] text-slate-600 line-clamp-2 italic">
                            &quot;{c.snippet}&quot;
                          </p>
                        </div>
                        {c.verified && (
                          <span className="shrink-0 text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                            Verified Citation
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Sections Browser */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-600" />
              <span>Statutory Sections & Clauses</span>
              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-mono font-semibold">
                {initialSections.length} sections
              </span>
            </h2>
            <p className="text-xs text-slate-500">
              Structured clauses extracted from official gazette text. Click the copy icon to share permalink.
            </p>
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={sectionFilter}
              onChange={(e) => setSectionFilter(e.target.value)}
              placeholder="Filter sections (e.g. 15, tax, penalty)..."
              className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 text-xs focus:outline-none focus:border-slate-400"
            />
          </div>
        </div>

        {filteredSections.length === 0 ? (
          <div className="p-8 text-center rounded-2xl bg-white border border-slate-200">
            <p className="text-xs text-slate-500">No sections matched your filter.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredSections.map((sec) => (
              <div
                key={sec.id}
                id={sec.number_label}
                className="p-5 rounded-2xl bg-white border border-slate-200 hover:border-slate-300 transition-all shadow-2xs space-y-2 group"
              >
                <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-lg bg-indigo-50 border border-indigo-100 font-mono text-xs font-bold text-indigo-700">
                      {sec.number_label}
                    </span>
                    {sec.heading && (
                      <h4 className="text-xs font-bold text-slate-900">
                        {sec.heading}
                      </h4>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleCopyLink(sec.id, sec.number_label)}
                    title="Copy section permalink"
                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    {copiedSectionId === sec.id ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                <div className="text-xs sm:text-sm text-slate-800 leading-relaxed font-serif whitespace-pre-wrap">
                  {sec.text}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Analyze SOP Modal */}
      {isAnalyzeModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-3xl bg-white border border-slate-200 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Scale className="w-4 h-4 text-emerald-600" />
                <span>Benchmark SOP Against Law</span>
              </h3>
              <button
                type="button"
                onClick={() => setIsAnalyzeModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 text-xs font-semibold"
              >
                Cancel
              </button>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Run the full 5-agent pipeline comparing your uploaded company SOP document against{' '}
              <strong className="text-slate-900">{law.canonical_title_en}</strong> to detect gaps, penalties, and mathematical evidence scores.
            </p>

            <form onSubmit={handleRunAnalyze} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Document ID (Uploaded SOP)
                </label>
                <input
                  type="text"
                  value={sopDocId}
                  onChange={(e) => setSopDocId(e.target.value)}
                  placeholder="e.g. doc_123 or paste from /upload"
                  required
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:border-slate-400 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Company Profile ID
                </label>
                <input
                  type="text"
                  value={companyProfileId}
                  onChange={(e) => setCompanyProfileId(e.target.value)}
                  placeholder="e.g. default or your company profile ID"
                  required
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:border-slate-400 font-mono"
                />
              </div>

              {analyzeError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{analyzeError}</span>
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAnalyzeModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAnalyzing || !sopDocId.trim() || !companyProfileId.trim()}
                  className="px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-semibold transition-colors flex items-center gap-1.5"
                >
                  {isAnalyzing ? 'Running 5 Agents...' : 'Start Multi-Agent Analysis'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Mandatory Legal Disclaimer */}
      <LegalDisclaimer />
    </div>
  );
}
