'use client';
import React, { useState, useEffect } from 'react';
import { FileText, ShieldAlert, CheckCircle2, RefreshCw, FileDiff, Hash } from 'lucide-react';
import { detectRegulationChange } from '@/lib/api';
import { RegulationChangeResponse } from '@/lib/types';

export default function RegulationsPage() {
  const [data, setData] = useState<RegulationChangeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchChange = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await detectRegulationChange();
      setData(res);
    } catch (err: any) {
      console.error(err);
      setError('Failed to fetch regulation diff from Watcher Agent.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChange();
  }, []);

  const beforeText = `National Board of Revenue (NBR) Value Added Tax (VAT) SRO Clause 4.2 (2024 Edition):

1. General Obligations:
All registered taxable entities operating in Bangladesh shall prepare and file their monthly VAT returns (Form Mushak-9.1) within thirty (30) calendar days following the conclusion of each monthly tax period.

2. Delegation of Responsibility:
General finance and accounting department staff are authorized to assemble, review, and submit the return documentation on behalf of the registered business entity. No individual designation is mandated.`;

  const afterText = `National Board of Revenue (NBR) Value Added Tax (VAT) SRO Clause 4.2 (2025 Revised Edition):

1. Filing Deadlines:
All registered taxable entities operating in Bangladesh shall prepare and file their monthly VAT returns (Form Mushak-9.1) within fifteen (15) calendar days following the conclusion of each monthly tax period.

2. Mandatory Designated Officer:
Every taxable entity must formally designate a named, certified VAT Filing Officer who bears primary legal responsibility for monthly VAT compliance, return verification, and digital signature submission.

3. Non-Compliance Penalties:
Failure to submit Form Mushak-9.1 within the mandatory 15-calendar-day window by the designated VAT Filing Officer shall trigger an automated non-compliance penalty of BDT 10,000 per day of delay.`;

  return (
    <div className="space-y-8">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-700 mb-1">
            <ShieldAlert className="w-4 h-4 text-amber-600" />
            <span>Agent 1 — Watcher Output</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Regulatory Change Watcher</h1>
          <p className="text-sm text-slate-500 mt-1">
            Diffing fixture regulation pair (`regulation_before.txt` vs `regulation_after.txt`)
          </p>
        </div>

        <button
          onClick={fetchChange}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-sm font-semibold transition-all shrink-0 shadow-2xs"
        >
          <RefreshCw className={`w-4 h-4 text-emerald-600 ${loading ? 'animate-spin' : ''}`} />
          <span>Re-Run Watcher Agent</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
          {error}
        </div>
      )}

      {/* Watcher Summary Card */}
      {data && (
        <div className="bg-white border border-slate-200/90 rounded-3xl p-6 space-y-6 shadow-2xs">
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
            <div>
              <h2 className="text-xl font-bold text-slate-900">{data.title}</h2>
              <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                <span className="flex items-center gap-1 font-mono text-emerald-700 font-semibold">
                  <Hash className="w-3.5 h-3.5" />
                  Hash: {data.version_hash}
                </span>
                <span>•</span>
                <span>Jurisdiction: Bangladesh (NBR)</span>
              </div>
            </div>

            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 uppercase tracking-wider">
              {data.change_type}
            </span>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Watcher Plain-Language Summary</h4>
            <p className="text-sm text-slate-800 leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200/80">
              "{data.change_summary}"
            </p>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Affected Regulatory Clauses</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {data.changed_clauses.map((clause, idx) => (
                <div key={idx} className="flex items-start gap-2.5 p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700 font-medium">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{clause}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Redline Text Diff View */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-base font-bold text-slate-900">
          <FileDiff className="w-5 h-5 text-emerald-600" />
          <h3>Cryptographic Regulation Text Diff</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* Before Text */}
          <div className="bg-white border border-rose-200 rounded-3xl p-5 space-y-3 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-rose-100">
              <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">Before — 2024 SRO Edition</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 font-mono font-medium">regulation_before.txt</span>
            </div>
            <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200">
              {beforeText}
            </pre>
          </div>

          {/* After Text */}
          <div className="bg-white border border-emerald-200 rounded-3xl p-5 space-y-3 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-emerald-100">
              <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">After — 2025 Revised Edition</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono font-medium">regulation_after.txt</span>
            </div>
            <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200">
              {afterText}
            </pre>
          </div>

        </div>
      </div>

    </div>
  );
}
