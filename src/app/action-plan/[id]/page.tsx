'use client';
import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Download, AlertTriangle, CheckCircle2, FileText, Code2, Scale, ArrowLeft, RefreshCw, CheckSquare } from 'lucide-react';
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
        <RefreshCw className="w-8 h-8 text-emerald-600 animate-spin" />
        <p className="text-sm font-medium text-slate-500">Retrieving Compliance Action Plan Report...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-xl mx-auto text-center space-y-4 py-16">
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-slate-900">Action Plan Not Found</h2>
        <p className="text-xs text-slate-500">{error || 'The requested action plan could not be retrieved.'}</p>
        <Link
          href="/analysis"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Analysis</span>
        </Link>
      </div>
    );
  }

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

        <a
          href={getDownloadReportUrl(data.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-sm transition-all shrink-0"
        >
          <Download className="w-4 h-4" />
          <span>Export Markdown Audit Report (.md)</span>
        </a>
      </div>

      {/* Header Executive Card */}
      <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xs">
        
        <div className="flex flex-wrap items-start justify-between gap-6 pb-6 border-b border-slate-100">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">Organization:</span>
              <span className="text-sm font-semibold text-slate-900">{data.company}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Compliance Audit Report: <span className="text-emerald-700">{data.regulation}</span>
            </h1>
          </div>

          {/* Metrics */}
          <div className="flex items-center gap-3">
            
            <div className="bg-slate-50 border border-slate-200 p-3 rounded-2xl text-center min-w-[100px]">
              <div className="text-2xl font-black text-rose-600">{data.impact_score}<span className="text-xs text-slate-400 font-normal">/100</span></div>
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mt-0.5">Impact Risk Score</div>
            </div>

            <div className="bg-slate-50 border border-slate-200 p-3 rounded-2xl text-center min-w-[100px]">
              <div className="text-sm font-extrabold uppercase text-amber-700">{data.urgency}</div>
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mt-0.5">Urgency Level</div>
            </div>

          </div>
        </div>

        {/* Change Summary */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Watcher Regulatory Change Summary</h4>
          <p className="text-sm text-slate-800 leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200">
            "{data.change_summary}"
          </p>
        </div>

      </div>

      {/* Legal Notice */}
      <LegalDisclaimer />

      {/* Section 1: Verified Findings & Citations */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-base font-bold text-slate-900">
          <Scale className="w-5 h-5 text-emerald-600" />
          <h2>1. Verified Compliance Findings & Evidence Citations</h2>
        </div>

        <div className="grid grid-cols-1 gap-4">
          {data.findings.map((f, idx) => {
            const isLowConfidence = f.flagged_for_review || f.confidence < 0.60;
            const confPct = Math.round(f.confidence * 100);

            return (
              <div
                key={idx}
                className={`bg-white border rounded-3xl p-6 space-y-4 shadow-2xs ${
                  isLowConfidence ? 'border-amber-300' : 'border-slate-200/90'
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
                    </div>
                    <h3 className="text-base font-bold text-slate-900 mt-1">{f.issue}</h3>
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
                    "{f.citation.text_snippet}"
                  </blockquote>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 2: Redlined Policy Amendments */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-base font-bold text-slate-900">
          <FileText className="w-5 h-5 text-emerald-600" />
          <h2>2. Redlined Policy Draft Amendments</h2>
        </div>

        <div className="bg-white border border-slate-200/90 rounded-3xl p-6 space-y-4 shadow-2xs">
          <p className="text-xs text-slate-500">
            SOP policy text amendments drafted by Agent 4 for regulatory compliance.
          </p>

          <div className="space-y-3">
            {data.policy_draft.map((draft, idx) => (
              <div key={idx} className="p-4 rounded-2xl bg-emerald-50/50 border border-emerald-200 text-xs text-emerald-950 leading-relaxed font-mono">
                <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-emerald-700 mb-2">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Policy Clause Amendment #{idx + 1}</span>
                </div>
                <div>{draft}</div>
              </div>
            ))}
          </div>
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
            {data.technical_fixes.map((fix, idx) => {
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
          </div>
        </div>
      </div>

    </div>
  );
}
