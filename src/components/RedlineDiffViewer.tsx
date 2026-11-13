'use client';

import React, { useState, useMemo } from 'react';
import {
  GitCompare,
  Columns,
  AlignLeft,
  Copy,
  Check,
  FileText,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

export interface RedlineDiffViewerProps {
  originalText?: string;
  revisedText: string;
  clauseTitle?: string;
  clauseIndex: number;
  availableSnippets?: { id: string; label: string; text: string }[];
}

type DiffMode = 'inline' | 'split' | 'clean';

interface DiffToken {
  type: 'equal' | 'insert' | 'delete';
  value: string;
}

// Tokenize keeping words and whitespace
function tokenize(text: string): string[] {
  return text.match(/\S+|\s+/g) || [];
}

// Classic Longest Common Subsequence (LCS) word-level diff
function computeLcsDiff(orig: string, rev: string): DiffToken[] {
  const a = tokenize(orig);
  const b = tokenize(rev);
  const n = a.length;
  const m = b.length;

  // DP table
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

  // Backtrack
  let i = n;
  let j = m;
  const result: DiffToken[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1].toLowerCase() === b[j - 1].toLowerCase()) {
      result.unshift({ type: 'equal', value: b[j - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'insert', value: b[j - 1] });
      j--;
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      result.unshift({ type: 'delete', value: a[i - 1] });
      i--;
    }
  }

  return result;
}

export function RedlineDiffViewer({
  originalText = '',
  revisedText,
  clauseTitle,
  clauseIndex,
  availableSnippets = [],
}: RedlineDiffViewerProps) {
  const [mode, setMode] = useState<DiffMode>('inline');
  const [selectedSnippetIdx, setSelectedSnippetIdx] = useState<number>(0);
  const [copied, setCopied] = useState(false);

  // Active original text to compare against
  const activeOriginal = useMemo(() => {
    if (availableSnippets.length > 0 && selectedSnippetIdx < availableSnippets.length) {
      return availableSnippets[selectedSnippetIdx].text;
    }
    return originalText;
  }, [availableSnippets, selectedSnippetIdx, originalText]);

  // Compute diff
  const diffTokens = useMemo(() => {
    if (!activeOriginal) {
      return [{ type: 'insert' as const, value: revisedText }];
    }
    return computeLcsDiff(activeOriginal, revisedText);
  }, [activeOriginal, revisedText]);

  // Compute statistics
  const stats = useMemo(() => {
    let addedWords = 0;
    let deletedWords = 0;
    let unchangedWords = 0;

    for (const t of diffTokens) {
      const words = t.value.trim().split(/\s+/).filter(Boolean).length;
      if (t.type === 'insert') addedWords += words;
      else if (t.type === 'delete') deletedWords += words;
      else unchangedWords += words;
    }

    const totalWords = unchangedWords + addedWords;
    return { addedWords, deletedWords, unchangedWords, totalWords };
  }, [diffTokens]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(revisedText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      setCopied(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-2xs transition-all">
      {/* Header Bar */}
      <div className="bg-slate-50/90 border-b border-slate-200 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-100 text-emerald-800 text-xs font-bold">
            #{clauseIndex + 1}
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-900">
              {clauseTitle || `Policy Clause Amendment #${clauseIndex + 1}`}
            </h4>
            <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
              <span className="flex items-center gap-1 text-emerald-700 font-medium">
                <TrendingUp className="w-3 h-3" /> +{stats.addedWords} added
              </span>
              <span>•</span>
              <span className="flex items-center gap-1 text-rose-600 font-medium">
                <TrendingDown className="w-3 h-3" /> -{stats.deletedWords} removed
              </span>
              {activeOriginal && (
                <>
                  <span>•</span>
                  <span>{stats.totalWords} words total</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* View Mode Toggle & Copy Action */}
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-xl bg-slate-200/70 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => setMode('inline')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition-all ${
                mode === 'inline'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              title="Track Changes / Redline View"
            >
              <GitCompare className="w-3.5 h-3.5 text-indigo-600" />
              <span className="hidden sm:inline">Track Changes</span>
            </button>
            <button
              type="button"
              onClick={() => setMode('split')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition-all ${
                mode === 'split'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              title="Side-by-Side Comparison"
            >
              <Columns className="w-3.5 h-3.5 text-indigo-600" />
              <span className="hidden sm:inline">Side-by-Side</span>
            </button>
            <button
              type="button"
              onClick={() => setMode('clean')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition-all ${
                mode === 'clean'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              title="Clean Policy Draft"
            >
              <AlignLeft className="w-3.5 h-3.5 text-emerald-600" />
              <span className="hidden sm:inline">Clean Draft</span>
            </button>
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
              copied
                ? 'bg-emerald-600 text-white border-emerald-600'
                : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
            }`}
            title="Copy clean clause to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-slate-500" />
                <span className="hidden sm:inline">Copy Clause</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Optional Selector if multiple citations available */}
      {availableSnippets.length > 1 && (
        <div className="bg-slate-50/50 border-b border-slate-100 px-4 py-2 flex items-center gap-2 text-xs">
          <span className="font-semibold text-slate-500 shrink-0">Compare with original:</span>
          <select
            value={selectedSnippetIdx}
            onChange={(e) => setSelectedSnippetIdx(Number(e.target.value))}
            className="text-xs rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {availableSnippets.map((s, idx) => (
              <option key={s.id} value={idx}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Main Diff Content Area */}
      <div className="p-4 sm:p-5 text-xs sm:text-sm leading-relaxed">
        {mode === 'inline' && (
          <div className="rounded-xl bg-slate-50/70 p-4 border border-slate-200 font-mono text-xs whitespace-pre-wrap leading-relaxed select-text">
            {diffTokens.map((token, idx) => {
              if (token.type === 'delete') {
                return (
                  <del
                    key={idx}
                    className="bg-rose-100 text-rose-800 line-through decoration-rose-500 px-1 py-0.5 rounded mx-0.5"
                  >
                    {token.value}
                  </del>
                );
              }
              if (token.type === 'insert') {
                return (
                  <ins
                    key={idx}
                    className="bg-emerald-100 text-emerald-950 no-underline font-semibold border-b-2 border-emerald-500 px-1 py-0.5 rounded mx-0.5"
                  >
                    {token.value}
                  </ins>
                );
              }
              return <span key={idx} className="text-slate-800">{token.value}</span>;
            })}
          </div>
        )}

        {mode === 'split' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left Column: Original SOP Text */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <FileText className="w-3.5 h-3.5 text-slate-400" />
                <span>Original SOP Section</span>
              </div>
              <div className="rounded-xl bg-rose-50/40 p-4 border border-rose-200 font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed min-h-[140px]">
                {activeOriginal ? (
                  diffTokens.map((token, idx) => {
                    if (token.type === 'delete') {
                      return (
                        <span
                          key={idx}
                          className="bg-rose-200 text-rose-950 font-semibold line-through decoration-rose-600 px-1 py-0.5 rounded mx-0.5"
                        >
                          {token.value}
                        </span>
                      );
                    }
                    if (token.type === 'insert') {
                      return null; // Don't show additions on the original side
                    }
                    return <span key={idx}>{token.value}</span>;
                  })
                ) : (
                  <span className="text-slate-400 italic font-sans">
                    No matching original SOP section snippet found for direct comparison.
                  </span>
                )}
              </div>
            </div>

            {/* Right Column: Amended Policy Draft */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                <span>Amended Policy Clause</span>
              </div>
              <div className="rounded-xl bg-emerald-50/40 p-4 border border-emerald-200 font-mono text-xs text-emerald-950 whitespace-pre-wrap leading-relaxed min-h-[140px]">
                {diffTokens.map((token, idx) => {
                  if (token.type === 'insert') {
                    return (
                      <span
                        key={idx}
                        className="bg-emerald-200 text-emerald-950 font-bold border-b border-emerald-600 px-1 py-0.5 rounded mx-0.5"
                      >
                        {token.value}
                      </span>
                    );
                  }
                  if (token.type === 'delete') {
                    return null; // Don't show deletions on the revised side
                  }
                  return <span key={idx}>{token.value}</span>;
                })}
              </div>
            </div>
          </div>
        )}

        {mode === 'clean' && (
          <div className="rounded-xl bg-emerald-50/30 p-4 border border-emerald-200/80 font-mono text-xs text-slate-900 whitespace-pre-wrap leading-relaxed">
            {revisedText}
          </div>
        )}

        {/* Legend */}
        {mode !== 'clean' && activeOriginal && (
          <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px] text-slate-500 pt-2 border-t border-slate-100">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              <span>Red strikethrough: Outdated/non-compliant text to replace</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span>Green highlight: Mandatory statutory wording drafted by Agent 4</span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
