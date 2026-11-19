'use client';

import React, { useState, useTransition, useMemo } from 'react';
import Link from 'next/link';
import {
  Download,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Code2,
  Scale,
  ArrowLeft,
  CheckSquare,
  Lock,
  MessageSquare,
  Send,
  XCircle,
  Edit3,
  UserCheck,
  Printer,
} from 'lucide-react';
import { ActionPlanResponse, CommentItem, FindingReviewItem } from '@/lib/types';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';
import { useAuth } from '@/context/AuthContext';
import { PlanBadge } from '@/components/PlanBadge';
import { RedlineDiffViewer } from '@/components/RedlineDiffViewer';
import { createComment, getComments, getDownloadReportUrl, submitFindingReview } from '@/lib/api';

interface ActionPlanClientProps {
  plan: ActionPlanResponse;
  initialReviews: FindingReviewItem[];
  initialAdjustedScore: number;
}

export function ActionPlanClient({
  plan,
  initialReviews,
  initialAdjustedScore,
}: ActionPlanClientProps) {
  const { hasCapability, openUpgradeModal } = useAuth();

  const [completedFixes, setCompletedFixes] = useState<Record<number, boolean>>({});
  const [reviews, setReviews] = useState<Record<string, FindingReviewItem>>(() => {
    const map: Record<string, FindingReviewItem> = {};
    for (const r of initialReviews) {
      map[r.finding_id] = r;
    }
    return map;
  });
  const [adjustedScore, setAdjustedScore] = useState<number>(initialAdjustedScore);

  // Comments state per finding
  const [activeCommentsFindingId, setActiveCommentsFindingId] = useState<string | null>(null);
  const [commentsMap, setCommentsMap] = useState<Record<string, CommentItem[]>>({});
  const [newCommentText, setNewCommentText] = useState('');
  const [editingCitationFindingId, setEditingCitationFindingId] = useState<string | null>(null);
  const [editCitationText, setEditCitationText] = useState('');
  const [editNoteText, setEditNoteText] = useState('');

  const [isPending, startTransition] = useTransition();

  const availableSnippets = useMemo(() => {
    return plan.findings
      .filter((f) => f.citation && f.citation.text_snippet)
      .map((f, idx) => ({
        id: f.id || String(idx),
        label: `${f.citation.source.toUpperCase()}: ${f.citation.section || f.issue}`,
        text: f.citation.text_snippet,
      }));
  }, [plan.findings]);

  const toggleFix = (idx: number) => {
    setCompletedFixes((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const handleReviewStatus = (
    findingId: string,
    status: 'approved' | 'rejected' | 'edited',
    note?: string,
    editedCitation?: string
  ) => {
    startTransition(async () => {
      try {
        const res = await submitFindingReview(plan.id, findingId, status, note, editedCitation);
        setReviews((prev) => ({ ...prev, [findingId]: res.review }));
        setAdjustedScore(res.adjusted_impact_score);
        setEditingCitationFindingId(null);
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Failed to submit review.');
      }
    });
  };

  const handleToggleComments = (findingId: string) => {
    if (activeCommentsFindingId === findingId) {
      setActiveCommentsFindingId(null);
      return;
    }
    setActiveCommentsFindingId(findingId);
    if (!commentsMap[findingId]) {
      startTransition(async () => {
        try {
          const list = await getComments('finding', findingId);
          setCommentsMap((prev) => ({ ...prev, [findingId]: list }));
        } catch (e) {
          console.error('Failed to load comments', e);
        }
      });
    }
  };

  const handlePostComment = (findingId: string) => {
    if (!newCommentText.trim()) return;
    const text = newCommentText.trim();
    setNewCommentText('');

    startTransition(async () => {
      try {
        const cmt = await createComment('finding', findingId, text);
        setCommentsMap((prev) => ({
          ...prev,
          [findingId]: [...(prev[findingId] || []), cmt],
        }));
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Failed to post comment.');
      }
    });
  };

  const hasAdjustedScore = adjustedScore !== plan.impact_score;

  return (
    <div className="space-y-8">
      {/* Top Breadcrumb & Download CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <Link
          href="/analysis"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Analysis Pipeline</span>
        </Link>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-800 font-semibold text-xs shadow-2xs transition-all shrink-0 no-print"
            title="Print official audit report or save as PDF"
          >
            <Printer className="w-4 h-4 text-slate-600" />
            <span>Print Report (PDF)</span>
          </button>

          {hasCapability('report_download', 'basic') ? (
            <a
              href={getDownloadReportUrl(plan.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-xs transition-all shrink-0 no-print"
            >
              <Download className="w-4 h-4" />
              <span>Export Markdown (.md)</span>
            </a>
          ) : (
            <button
              type="button"
              onClick={() => openUpgradeModal('Markdown Audit Reports', 'starter')}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-300 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-all shrink-0 no-print"
            >
              <Lock className="w-4 h-4 text-slate-500" />
              <span>Export Report (Starter)</span>
            </button>
          )}
        </div>
      </div>

      {/* Header Executive Card */}
      <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xs">
        <div className="flex flex-wrap items-start justify-between gap-6 pb-6 border-b border-slate-100">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">Organization:</span>
              <span className="text-sm font-semibold text-slate-900">{plan.company}</span>
              {plan.plan_tier && <PlanBadge planId={plan.plan_tier} size="sm" />}
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1 font-semibold text-slate-700">
                <FileText className="w-3.5 h-3.5 text-emerald-600" />
                {plan.document_name}
              </span>
              <span>•</span>
              <span className="font-mono text-[11px]">hash: {plan.regulation_version_hash}</span>
              <span>•</span>
              <span className="font-mono text-[11px]">model: {plan.model}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Compliance Audit Report: <span className="text-emerald-700">{plan.regulation}</span>
            </h1>
          </div>

          {/* Metrics */}
          <div className="flex items-center gap-3">
            {/* Impact Risk Score */}
            <div className="bg-slate-50 border border-slate-200 p-3 rounded-2xl text-center min-w-[120px]">
              {hasAdjustedScore ? (
                <div>
                  <div className="flex items-baseline justify-center gap-1.5">
                    <span className="text-2xl font-black text-emerald-600">{adjustedScore}</span>
                    <span className="text-xs line-through text-slate-400 font-mono">{plan.impact_score}</span>
                  </div>
                  <div className="text-[10px] uppercase tracking-wider font-bold text-emerald-700 flex items-center justify-center gap-1 mt-0.5">
                    <UserCheck className="w-3 h-3" />
                    <span>Adjusted Risk</span>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="text-2xl font-black text-rose-600">
                    {plan.impact_score}
                    <span className="text-xs text-slate-400 font-normal">/100</span>
                  </div>
                  <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mt-0.5">
                    Impact Risk Score
                  </div>
                </div>
              )}
            </div>

            <div className="bg-slate-50 border border-slate-200 p-3 rounded-2xl text-center min-w-[100px]">
              <div className="text-sm font-extrabold uppercase text-amber-700">{plan.urgency}</div>
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mt-0.5">
                Urgency Level
              </div>
            </div>
          </div>
        </div>

        {/* Change Summary */}
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Watcher Regulatory Change Summary
          </h2>
          <p className="text-sm text-slate-800 leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200">
            &ldquo;{plan.change_summary}&rdquo;
          </p>
        </div>
      </div>

      {/* Legal Notice */}
      <LegalDisclaimer />

      {/* Section 1: Verified Findings & Citations */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-base font-bold text-slate-900">
            <Scale className="w-5 h-5 text-emerald-600" />
            <h2>1. Verified Compliance Findings & Citations</h2>
          </div>
          <span className="text-xs text-slate-500">Human-in-the-loop review enabled</span>
        </div>

        <div className="grid grid-cols-1 gap-4">
          {plan.findings.map((f, idx) => {
            const isLowConfidence = f.flagged_for_review || f.confidence < 0.6;
            const confPct = Math.round(f.confidence * 100);
            const review = reviews[f.id];
            const isCommentsOpen = activeCommentsFindingId === f.id;
            const commentsList = commentsMap[f.id] || [];

            return (
              <div
                key={f.id || idx}
                className={`bg-white border rounded-3xl p-6 space-y-4 shadow-2xs transition-all ${
                  review?.status === 'rejected'
                    ? 'border-slate-200 opacity-60 bg-slate-50/50'
                    : review?.status === 'approved'
                    ? 'border-emerald-300 bg-white'
                    : isLowConfidence
                    ? 'border-amber-300'
                    : 'border-slate-200/90'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200">
                        {f.issue_type}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-200">
                        {f.severity} severity
                      </span>
                      {review && (
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                            review.status === 'approved'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : review.status === 'rejected'
                              ? 'bg-rose-50 text-rose-700 border-rose-200'
                              : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                          }`}
                        >
                          Reviewed: {review.status}
                        </span>
                      )}
                    </div>
                    <h3
                      className={`text-base font-bold text-slate-900 mt-1 ${
                        review?.status === 'rejected' ? 'line-through text-slate-500' : ''
                      }`}
                    >
                      {f.issue}
                    </h3>
                  </div>

                  {/* Confidence Pill */}
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-bold font-mono border flex items-center gap-1.5 ${
                        isLowConfidence
                          ? 'bg-amber-50 text-amber-800 border-amber-200'
                          : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      }`}
                    >
                      {isLowConfidence ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      )}
                      <span>{confPct}% Confidence</span>
                    </span>

                    {isLowConfidence && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200 uppercase">
                        Review Flagged
                      </span>
                    )}

                    {(f.is_ocr || f.citation?.is_ocr) && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-50 text-purple-800 border border-purple-200 uppercase">
                        OCR-extracted, review recommended
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed">{f.explanation}</p>

                {/* Verified Citation Box */}
                <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-600 font-semibold">
                    <span className="flex items-center gap-1.5 text-emerald-700">
                      <FileText className="w-3.5 h-3.5" />
                      Citation Ref: {f.citation.source} ({f.citation.section})
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">Verified Match</span>
                  </div>
                  <blockquote className="italic text-slate-800 border-l-2 border-emerald-600 pl-3 py-0.5">
                    &ldquo;{review?.edited_citation || f.citation.text_snippet}&rdquo;
                  </blockquote>
                  {review?.note && (
                    <div className="text-[11px] text-indigo-700 font-medium bg-indigo-50/80 p-2 rounded-lg border border-indigo-100 mt-2">
                      Reviewer Note: {review.note}
                    </div>
                  )}
                </div>

                {/* Human-in-the-loop Review Controls & Comments Toggle */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-semibold text-slate-500">Human Review:</span>
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handleReviewStatus(f.id, 'approved')}
                      className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                        review?.status === 'approved'
                          ? 'bg-emerald-600 text-white shadow-2xs'
                          : 'bg-slate-100 hover:bg-emerald-50 text-slate-700 hover:text-emerald-700'
                      }`}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Approve</span>
                    </button>

                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handleReviewStatus(f.id, 'rejected')}
                      className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                        review?.status === 'rejected'
                          ? 'bg-rose-600 text-white shadow-2xs'
                          : 'bg-slate-100 hover:bg-rose-50 text-slate-700 hover:text-rose-700'
                      }`}
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setEditingCitationFindingId(editingCitationFindingId === f.id ? null : f.id);
                        setEditCitationText(f.citation.text_snippet);
                        setEditNoteText(review?.note || '');
                      }}
                      className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 flex items-center gap-1"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      <span>Edit</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleToggleComments(f.id)}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Discussion ({commentsList.length})</span>
                  </button>
                </div>

                {/* Inline Edit Form */}
                {editingCitationFindingId === f.id && (
                  <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-200 space-y-3">
                    <h4 className="text-xs font-bold text-indigo-900">Edit Citation & Add Reviewer Note</h4>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                        Adjusted Statutory Citation Snippet
                      </label>
                      <textarea
                        rows={2}
                        value={editCitationText}
                        onChange={(e) => setEditCitationText(e.target.value)}
                        className="w-full text-xs p-2.5 rounded-xl border border-indigo-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                        Reviewer Note / Justification
                      </label>
                      <input
                        type="text"
                        value={editNoteText}
                        placeholder="e.g. Clause amended per NBR Statutory Order 2026/04."
                        onChange={(e) => setEditNoteText(e.target.value)}
                        className="w-full text-xs p-2 rounded-xl border border-indigo-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setEditingCitationFindingId(null)}
                        className="px-3 py-1 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        disabled={isPending}
                        onClick={() =>
                          handleReviewStatus(f.id, 'edited', editNoteText, editCitationText)
                        }
                        className="px-3 py-1 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-500"
                      >
                        Save Edited Citation
                      </button>
                    </div>
                  </div>
                )}

                {/* Comments Thread */}
                {isCommentsOpen && (
                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
                    <h4 className="text-xs font-bold text-slate-900">Team Discussion</h4>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {commentsList.length === 0 ? (
                        <p className="text-xs text-slate-400 italic">
                          No comments yet. Start the conversation below.
                        </p>
                      ) : (
                        commentsList.map((cmt) => (
                          <div
                            key={cmt.id}
                            className="p-2.5 rounded-xl bg-white border border-slate-200 text-xs space-y-1 shadow-2xs"
                          >
                            <div className="flex items-center justify-between text-[11px] text-slate-500">
                              <span className="font-semibold text-slate-800">
                                {cmt.full_name || cmt.email?.split('@')[0] || 'Team Member'}
                              </span>
                              <span>{new Date(cmt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>
                            <p className="text-slate-700">{cmt.content}</p>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <input
                        type="text"
                        placeholder="Add your note or inquiry..."
                        value={newCommentText}
                        onChange={(e) => setNewCommentText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handlePostComment(f.id);
                        }}
                        className="w-full text-xs px-3 py-2 rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <button
                        type="button"
                        disabled={isPending || !newCommentText.trim()}
                        onClick={() => handlePostComment(f.id)}
                        className="p-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
                      >
                        <Send className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {plan.locked?.find((l) => l.section === 'findings') && (
            <div className="p-4 rounded-2xl border border-dashed border-amber-300 bg-amber-50/60 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2 text-amber-900">
                <Lock className="w-4 h-4 shrink-0 text-amber-600" />
                <span>
                  <strong>{plan.locked.find((l) => l.section === 'findings')?.hidden_count} additional findings</strong> hidden in this tier.
                </span>
              </div>
              <button
                type="button"
                onClick={() => openUpgradeModal('Full Regulatory Findings', 'growth')}
                className="px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs transition-all shrink-0"
              >
                Upgrade to Growth
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Section 2: Redlined Policy Amendments */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-base font-bold text-slate-900">
            <FileText className="w-5 h-5 text-emerald-600" />
            <h2>2. Interactive Policy Redlines & Amendments</h2>
          </div>
          <span className="text-xs text-slate-500 font-medium hidden sm:inline">
            Drafted by Agent 4 • Word-level LCS Diff Engine
          </span>
        </div>

        <div className="space-y-4">
          {plan.policy_draft.length === 0 ? (
            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 text-center text-xs text-slate-500 shadow-2xs">
              No policy clause rewrites required for this SOP.
            </div>
          ) : (
            plan.policy_draft.map((draft, idx) => {
              // Try to pair draft with finding that mentions the same section, or by matching SOP citation
              const matchedFinding =
                plan.findings.find(
                  (f) =>
                    f.citation?.text_snippet &&
                    f.citation.source.toLowerCase() === 'sop' &&
                    f.citation.section &&
                    draft.toLowerCase().includes(f.citation.section.toLowerCase())
                ) ||
                plan.findings.find(
                  (f) => f.citation?.text_snippet && f.citation.source.toLowerCase() === 'sop'
                ) ||
                plan.findings[idx];

              const origText = matchedFinding?.citation?.text_snippet || '';

              return (
                <RedlineDiffViewer
                  key={idx}
                  clauseIndex={idx}
                  clauseTitle={`Policy Clause Amendment #${idx + 1}`}
                  revisedText={draft}
                  originalText={origText}
                  availableSnippets={availableSnippets}
                />
              );
            })
          )}
        </div>
      </div>

      {/* Section 3: Engineering Technical Fixes */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-base font-bold text-slate-900">
          <Code2 className="w-5 h-5 text-emerald-600" />
          <h2>3. Actionable Engineering Technical Fixes</h2>
        </div>

        <div className="bg-white border border-slate-200/90 rounded-3xl p-6 space-y-4 shadow-2xs">
          <p className="text-xs text-slate-500">
            Mandatory internal operational and software changes required across tax and administrative portals.
          </p>

          <div className="space-y-2.5">
            {plan.technical_fixes.map((fix, idx) => {
              const isChecked = Boolean(completedFixes[idx]);
              return (
                <div
                  key={idx}
                  onClick={() => toggleFix(idx)}
                  className={`p-3.5 rounded-2xl border cursor-pointer flex items-center gap-3 transition-all ${
                    isChecked
                      ? 'bg-emerald-50/60 border-emerald-200 text-slate-400 line-through'
                      : 'bg-slate-50 border-slate-200 text-slate-800 hover:border-slate-300'
                  }`}
                >
                  <div
                    className={`w-4.5 h-4.5 rounded-md flex items-center justify-center shrink-0 border transition-all ${
                      isChecked
                        ? 'bg-emerald-600 border-emerald-600 text-white'
                        : 'border-slate-300 bg-white'
                    }`}
                  >
                    {isChecked && <CheckSquare className="w-3.5 h-3.5" />}
                  </div>
                  <span className="text-xs font-medium">{fix}</span>
                </div>
              );
            })}

            {plan.locked?.find((l) => l.section === 'technical_fixes') && (
              <div className="p-4 rounded-2xl border border-dashed border-indigo-300 bg-indigo-50/60 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2 text-indigo-900">
                  <Lock className="w-4 h-4 shrink-0 text-indigo-600" />
                  <span>
                    Technical operational recommendations are locked on your current plan.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => openUpgradeModal('Technical Fixes', 'growth')}
                  className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-all shrink-0"
                >
                  Upgrade to Growth
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Section 4: Statutory Audit Certification & Executive Sign-off */}
      <div className="rounded-3xl border border-slate-200/90 bg-white p-6 sm:p-8 space-y-6 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-600 text-white font-extrabold text-sm tracking-wider shadow-2xs">
              NBR
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Statutory Compliance Verification Statement
              </h3>
              <p className="text-xs text-slate-500">
                Generated per Bangladesh Value Added Tax & Supplementary Duty Act 2012 / SRO Clause 4.2
              </p>
            </div>
          </div>
          <div className="text-left sm:text-right text-xs text-slate-500 font-mono space-y-0.5">
            <div>Plan ID: <span className="font-semibold text-slate-700">{plan.id.slice(0, 14)}...</span></div>
            <div>Integrity Hash: <span className="font-semibold text-slate-700">{plan.regulation_version_hash}</span></div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-2 text-xs">
          <div className="space-y-1.5">
            <div className="font-semibold text-slate-700">Verification Protocol</div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 font-bold text-[11px]">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Deterministic RapidFuzz Algorithm</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Zero hallucination risk. Citations mathematically bound to source text.
            </p>
          </div>

          <div className="space-y-1.5">
            <div className="font-semibold text-slate-700">Audit Timestamp</div>
            <div className="text-slate-800 font-mono text-xs">
              {new Date(plan.created_at).toLocaleString('en-US', { timeZone: 'Asia/Dhaka' })} BST
            </div>
            <p className="text-[11px] text-slate-500">
              Evaluated by AI Engine: <span className="font-mono">{plan.model}</span>
            </p>
          </div>

          <div className="space-y-2">
            <div className="font-semibold text-slate-700">Corporate Sign-Off & Seal</div>
            <div className="mt-4 pt-6 border-b border-dashed border-slate-400" />
            <div className="text-slate-500 text-[11px] flex justify-between">
              <span>Authorized Officer Signature</span>
              <span>Date</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
