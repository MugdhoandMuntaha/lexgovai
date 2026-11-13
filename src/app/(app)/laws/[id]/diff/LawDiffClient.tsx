'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  GitCompare,
  PlusCircle,
  MinusCircle,
  Edit3,
  CheckCircle,
  Layers,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { LawDetailResponse } from '@/lib/types';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

interface LawDiffClientProps {
  detail: LawDetailResponse;
  diffData: {
    law_id: string;
    from_version_id: string;
    to_version_id: string;
    diffs: Array<{
      number_label: string;
      heading?: string | null;
      change_type: 'added' | 'removed' | 'modified' | 'unchanged';
      old_text?: string | null;
      new_text?: string | null;
    }>;
  } | null;
  selectedFromId?: string;
  selectedToId?: string;
}

// Word-level diff tokenizer
function tokenize(text: string): string[] {
  return text.match(/\S+|\s+/g) || [];
}

interface DiffToken {
  type: 'equal' | 'insert' | 'delete';
  value: string;
}

function computeWordDiff(orig: string, rev: string): DiffToken[] {
  const a = tokenize(orig);
  const b = tokenize(rev);
  const n = a.length;
  const m = b.length;

  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < m; j++) {
      if (a[i].toLowerCase() === b[j].toLowerCase()) {
        dp[i + 1][j + 1] = dp[i][j] + 1;
      } else {
        dp[i + 1][j + 1] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  let i = n;
  let j = m;
  const tokens: DiffToken[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1].toLowerCase() === b[j - 1].toLowerCase()) {
      tokens.unshift({ type: 'equal', value: b[j - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      tokens.unshift({ type: 'insert', value: b[j - 1] });
      j--;
    } else if (i > 0) {
      tokens.unshift({ type: 'delete', value: a[i - 1] });
      i--;
    }
  }

  return tokens;
}

export function LawDiffClient({
  detail,
  diffData,
  selectedFromId,
  selectedToId,
}: LawDiffClientProps) {
  const router = useRouter();
  const { law, versions } = detail;

  const [fromVersionId, setFromVersionId] = useState(
    selectedFromId || diffData?.from_version_id || (versions.length >= 2 ? versions[1].id : versions[0]?.id || '')
  );
  const [toVersionId, setToVersionId] = useState(
    selectedToId || diffData?.to_version_id || versions[0]?.id || ''
  );
  const [changesOnly, setChangesOnly] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  const handleApplyVersions = () => {
    if (fromVersionId && toVersionId) {
      router.push(
        `/laws/${law.id}/diff?from_version_id=${encodeURIComponent(fromVersionId)}&to_version_id=${encodeURIComponent(toVersionId)}`
      );
    }
  };

  const diffs = useMemo(() => diffData?.diffs || [], [diffData]);

  const counts = useMemo(() => {
    let added = 0;
    let modified = 0;
    let removed = 0;
    let unchanged = 0;
    for (const d of diffs) {
      if (d.change_type === 'added') added++;
      else if (d.change_type === 'modified') modified++;
      else if (d.change_type === 'removed') removed++;
      else unchanged++;
    }
    return { added, modified, removed, unchanged, total: diffs.length };
  }, [diffs]);

  const displayedDiffs = useMemo(() => {
    if (!changesOnly) return diffs;
    return diffs.filter((d) => d.change_type !== 'unchanged');
  }, [diffs, changesOnly]);

  const toggleSection = (label: string) => {
    setExpandedSections((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  return (
    <div className="space-y-8 py-4">
      {/* Back button */}
      <div>
        <Link
          href={`/laws/${law.id}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to {law.canonical_title_en}</span>
        </Link>
      </div>

      {/* Header Card */}
      <div className="p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-5">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold uppercase tracking-wider">
            <GitCompare className="w-3.5 h-3.5" />
            <span>Version Comparison & Redline Diff</span>
          </div>
          <h1 className="text-xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {law.canonical_title_en}
          </h1>
          {law.canonical_title_bn && (
            <p className="text-xs text-slate-500 font-sans">{law.canonical_title_bn}</p>
          )}
        </div>

        {/* Version Selector Bar */}
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/90 flex flex-col sm:flex-row items-center gap-3">
          <div className="flex-1 w-full sm:w-auto grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                Base Edition (Older)
              </label>
              <select
                value={fromVersionId}
                onChange={(e) => setFromVersionId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-800 text-xs font-medium focus:outline-none focus:border-indigo-400"
              >
                {versions.map((v, i) => (
                  <option key={v.id} value={v.id}>
                    Version {versions.length - i} (Hash: {v.version_hash.slice(0, 8)}) - {v.fetched_at?.slice(0, 10)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                Target Edition (Newer)
              </label>
              <select
                value={toVersionId}
                onChange={(e) => setToVersionId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-800 text-xs font-medium focus:outline-none focus:border-indigo-400"
              >
                {versions.map((v, i) => (
                  <option key={v.id} value={v.id}>
                    Version {versions.length - i} (Hash: {v.version_hash.slice(0, 8)}) {v.is_current ? '★ Current' : ''} - {v.fetched_at?.slice(0, 10)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="button"
            onClick={handleApplyVersions}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors mt-auto self-end"
          >
            Compare Editions
          </button>
        </div>

        {/* Change Metrics Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="p-3.5 rounded-2xl bg-emerald-50/70 border border-emerald-200/80 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-800 text-xs font-bold">
              <PlusCircle className="w-4 h-4 text-emerald-600" />
              <span>Added Clauses</span>
            </div>
            <p className="text-xl font-mono font-extrabold text-emerald-900">{counts.added}</p>
          </div>

          <div className="p-3.5 rounded-2xl bg-amber-50/70 border border-amber-200/80 space-y-1">
            <div className="flex items-center gap-1.5 text-amber-800 text-xs font-bold">
              <Edit3 className="w-4 h-4 text-amber-600" />
              <span>Modified Clauses</span>
            </div>
            <p className="text-xl font-mono font-extrabold text-amber-900">{counts.modified}</p>
          </div>

          <div className="p-3.5 rounded-2xl bg-rose-50/70 border border-rose-200/80 space-y-1">
            <div className="flex items-center gap-1.5 text-rose-800 text-xs font-bold">
              <MinusCircle className="w-4 h-4 text-rose-600" />
              <span>Removed Clauses</span>
            </div>
            <p className="text-xl font-mono font-extrabold text-rose-900">{counts.removed}</p>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-100/70 border border-slate-200/80 space-y-1">
            <div className="flex items-center gap-1.5 text-slate-700 text-xs font-bold">
              <CheckCircle className="w-4 h-4 text-slate-500" />
              <span>Unchanged Clauses</span>
            </div>
            <p className="text-xl font-mono font-extrabold text-slate-800">{counts.unchanged}</p>
          </div>
        </div>
      </div>

      {/* Diff Sections List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600" />
            <span>Section-by-Section Redline Comparison</span>
            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-mono font-semibold">
              {displayedDiffs.length}
            </span>
          </h2>

          <div className="flex items-center gap-2">
            <label className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={changesOnly}
                onChange={(e) => setChangesOnly(e.target.checked)}
                className="rounded text-indigo-600 focus:ring-indigo-500"
              />
              <span>Show changes only ({counts.added + counts.modified + counts.removed})</span>
            </label>
          </div>
        </div>

        {displayedDiffs.length === 0 ? (
          <div className="p-12 text-center rounded-2xl bg-white border border-slate-200">
            <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-slate-900">No textual changes detected</h3>
            <p className="text-xs text-slate-500 mt-1">
              Both selected versions share identical statutory wording across all sections.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {displayedDiffs.map((diff) => {
              const isUnchanged = diff.change_type === 'unchanged';
              const isExpanded = expandedSections[diff.number_label] ?? !isUnchanged;

              return (
                <div
                  key={diff.number_label}
                  className={`rounded-2xl border transition-all ${
                    diff.change_type === 'added'
                      ? 'bg-emerald-50/30 border-emerald-200'
                      : diff.change_type === 'modified'
                      ? 'bg-amber-50/30 border-amber-200'
                      : diff.change_type === 'removed'
                      ? 'bg-rose-50/30 border-rose-200'
                      : 'bg-white border-slate-200'
                  }`}
                >
                  {/* Section Title Bar */}
                  <div
                    onClick={() => toggleSection(diff.number_label)}
                    className="p-4 flex items-center justify-between cursor-pointer select-none"
                  >
                    <div className="flex items-center gap-2.5">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      )}

                      <span className="font-mono text-xs font-bold text-slate-900">
                        {diff.number_label}
                      </span>

                      {diff.heading && (
                        <span className="text-xs font-semibold text-slate-800">
                          {diff.heading}
                        </span>
                      )}
                    </div>

                    <div>
                      {diff.change_type === 'added' && (
                        <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold uppercase tracking-wider">
                          + Added Section
                        </span>
                      )}
                      {diff.change_type === 'modified' && (
                        <span className="px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold uppercase tracking-wider">
                          ~ Modified Section
                        </span>
                      )}
                      {diff.change_type === 'removed' && (
                        <span className="px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 text-[10px] font-bold uppercase tracking-wider">
                          - Removed Section
                        </span>
                      )}
                      {diff.change_type === 'unchanged' && (
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-500 text-[10px] font-medium">
                          Unchanged
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Section Diff Content */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 border-t border-slate-100">
                      {diff.change_type === 'added' && (
                        <div className="p-3.5 rounded-xl bg-emerald-50/70 border border-emerald-200/80 text-xs sm:text-sm text-emerald-950 leading-relaxed font-serif whitespace-pre-wrap">
                          {diff.new_text}
                        </div>
                      )}

                      {diff.change_type === 'removed' && (
                        <div className="p-3.5 rounded-xl bg-rose-50/70 border border-rose-200/80 text-xs sm:text-sm text-rose-950 line-through leading-relaxed font-serif whitespace-pre-wrap">
                          {diff.old_text}
                        </div>
                      )}

                      {diff.change_type === 'modified' && diff.old_text && diff.new_text && (
                        <div className="space-y-3">
                          {/* Word-level redline view */}
                          <div className="p-4 rounded-xl bg-white border border-amber-200 text-xs sm:text-sm leading-relaxed font-serif space-y-1">
                            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 font-sans mb-1">
                              Redline View (Deletions & Insertions):
                            </div>
                            <div className="whitespace-pre-wrap">
                              {computeWordDiff(diff.old_text, diff.new_text).map((tok, i) => {
                                if (tok.type === 'delete') {
                                  return (
                                    <span
                                      key={i}
                                      className="bg-rose-100 text-rose-800 line-through px-0.5 rounded"
                                    >
                                      {tok.value}
                                    </span>
                                  );
                                }
                                if (tok.type === 'insert') {
                                  return (
                                    <span
                                      key={i}
                                      className="bg-emerald-100 text-emerald-900 font-semibold px-0.5 rounded"
                                    >
                                      {tok.value}
                                    </span>
                                  );
                                }
                                return <span key={i}>{tok.value}</span>;
                              })}
                            </div>
                          </div>
                        </div>
                      )}

                      {diff.change_type === 'unchanged' && (
                        <div className="p-3 rounded-xl bg-slate-50 text-xs text-slate-700 leading-relaxed font-serif whitespace-pre-wrap">
                          {diff.new_text || diff.old_text}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Mandatory Legal Disclaimer */}
      <LegalDisclaimer />
    </div>
  );
}
