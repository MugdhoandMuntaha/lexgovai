'use client';
import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { ShieldCheck, Download, AlertTriangle, CheckCircle2, FileText, Code2, Scale, ArrowLeft, RefreshCw, CheckSquare } from 'lucide-react';
import Link from 'next/link';
import { getActionPlan, getDownloadReportUrl } from '@/lib/api';
import { ActionPlanResponse } from '@/lib/types';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

export default function ActionPlanPage() {
  const params = useParams();
  const planId = params.id as string;

  const [data, setData] = useState<ActionPlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completedFixes, setCompletedFixes] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (planId) {
      getActionPlan(planId)
        .then((res) => {
          setData(res);
          setLoading(false);
        })
        .catch((err) => {
          console.error(err);
          setError('Action plan not found or failed to load.');
          setLoading(false);
        });
    }
  }, [planId]);

  const toggleFix = (idx: number) => {
    setCompletedFixes((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
        <p className="text-sm font-medium text-slate-400">Loading Compliance Action Plan...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-xl mx-auto text-center space-y-4 py-16">
        <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto" />
        <h2 className="text-xl font-bold text-white">Action Plan Not Found</h2>
        <p className="text-xs text-slate-400">{error || 'The requested action plan could not be retrieved.'}</p>
        <Link
          href="/analysis"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Analysis</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      
      {/* Top Breadcrumb & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <Link
          href="/analysis"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Analysis Launchpad</span>
        </Link>

        <a
          href={getDownloadReportUrl(data.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-lg shadow-indigo-600/30 transition-all shrink-0"
        >
          <Download className="w-4 h-4" />
          <span>Download Action Plan Report (.md)</span>
        </a>
      </div>

      {/* Header Banner */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xl backdrop-blur-md">
        
        <div className="flex flex-wrap items-start justify-between gap-6 pb-6 border-b border-slate-800">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">Company:</span>
              <span className="text-sm font-semibold text-white">{data.company}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Compliance Action Plan: <span className="text-indigo-400">{data.regulation}</span>
            </h1>
          </div>

          {/* Risk Metrics Badges */}
          <div className="flex items-center gap-4">
            
            {/* Impact Score Pill */}
            <div className="bg-slate-950/80 border border-slate-800 p-3 rounded-2xl text-center min-w-[100px]">
              <div className="text-2xl font-black text-rose-400">{data.impact_score}<span className="text-xs text-slate-500 font-normal">/100</span></div>
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 mt-0.5">Impact Score</div>
            </div>

            {/* Urgency Badge */}
            <div className="bg-slate-950/80 border border-slate-800 p-3 rounded-2xl text-center min-w-[100px]">
              <div className="text-sm font-extrabold uppercase text-amber-400">{data.urgency}</div>
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 mt-0.5">Urgency Level</div>
            </div>

          </div>
        </div>

        {/* Change Summary */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Watcher Regulatory Change Summary</h4>
          <p className="text-sm text-slate-200 leading-relaxed bg-slate-950/50 p-4 rounded-xl border border-slate-800">
            "{data.change_summary}"
          </p>
        </div>

      </div>

      {/* Legal Disclaimer */}
      <LegalDisclaimer />

      {/* Section 1: Verified Findings & Citations */}
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-lg font-bold text-white">
          <Scale className="w-5 h-5 text-indigo-400" />
          <h2>1. Verified Compliance Findings & Citations</h2>
        </div>

        <div className="grid grid-cols-1 gap-6">
          {data.findings.map((f, idx) => {
            const isLowConfidence = f.flagged_for_review || f.confidence < 0.60;
            const confPct = Math.round(f.confidence * 100);

            return (
              <div
                key={idx}
                className={`bg-slate-900/70 border rounded-2xl p-6 space-y-4 shadow-lg transition-all ${
                  isLowConfidence ? 'border-amber-500/40' : 'border-slate-800'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-500/10 text-rose-400 border border-rose-500/30">
                        {f.issue_type}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-300 border border-amber-500/30">
                        {f.severity} severity
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-white mt-1">{f.issue}</h3>
                  </div>

                  {/* Confidence Pill */}
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-bold font-mono border flex items-center gap-1.5 ${
                        isLowConfidence
                          ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                          : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      }`}
                    >
                      {isLowConfidence ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      )}
                      <span>{confPct}% Confidence</span>
                    </span>

                    {isLowConfidence && (
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 uppercase">
                        Flagged for Review
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-sm text-slate-300 leading-relaxed">{f.explanation}</p>

                {/* Verified Citation Box */}
                <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800 space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-400 font-semibold">
                    <span className="flex items-center gap-1.5 text-indigo-400">
                      <FileText className="w-3.5 h-3.5" />
                      Citation Ref: {f.citation.source} ({f.citation.section})
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">Critic Verification Match</span>
                  </div>
                  <blockquote className="italic text-slate-300 border-l-2 border-indigo-500 pl-3 py-0.5">
                    "{f.citation.text_snippet}"
                  </blockquote>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 2: Redlined Policy Drafts */}
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-lg font-bold text-white">
          <FileText className="w-5 h-5 text-indigo-400" />
          <h2>2. Redlined Policy Drafts</h2>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
          <p className="text-xs text-slate-400">
            Below are rewritten SOP policy clauses drafted by Agent 4 to ensure full compliance with the new NBR VAT regulation.
          </p>

          <div className="space-y-4">
            {data.policy_draft.map((draft, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-slate-950 border border-emerald-500/30 text-sm text-emerald-200 leading-relaxed font-mono">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-400 mb-2">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Draft Policy Amendment #{idx + 1}</span>
                </div>
                <div>{draft}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Section 3: Engineering Technical Fixes */}
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-lg font-bold text-white">
          <Code2 className="w-5 h-5 text-indigo-400" />
          <h2>3. Actionable Technical Fixes Checklist</h2>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
          <p className="text-xs text-slate-400">
            Concrete engineering and operational steps required across internal software and administrative portals.
          </p>

          <div className="space-y-3">
            {data.technical_fixes.map((fix, idx) => {
              const isChecked = Boolean(completedFixes[idx]);
              return (
                <div
                  key={idx}
                  onClick={() => toggleFix(idx)}
                  className={`p-3.5 rounded-xl border cursor-pointer flex items-center gap-3 transition-all ${
                    isChecked
                      ? 'bg-emerald-950/30 border-emerald-500/40 text-slate-400 line-through'
                      : 'bg-slate-950/60 border-slate-800 text-slate-200 hover:border-slate-700'
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-md flex items-center justify-center shrink-0 border transition-all ${
                      isChecked
                        ? 'bg-emerald-500 border-emerald-400 text-slate-950'
                        : 'border-slate-700 bg-slate-900'
                    }`}
                  >
                    {isChecked && <CheckSquare className="w-4 h-4" />}
                  </div>
                  <span className="text-sm font-medium">{fix}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

    </div>
  );
}
