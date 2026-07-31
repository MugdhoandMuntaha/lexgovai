'use client';
import React from 'react';
import Link from 'next/link';
import { ShieldAlert, ArrowRight, FileCheck, Cpu, UploadCloud, FileText, CheckCircle2, Zap } from 'lucide-react';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

export default function Home() {
  return (
    <div className="space-y-10">
      
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-b from-slate-900 via-slate-900/90 to-slate-950 p-8 sm:p-12 border border-slate-800 shadow-2xl">
        <div className="absolute top-0 right-0 -mt-12 -mr-12 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 -mb-12 w-80 h-80 bg-violet-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold">
            <Zap className="w-3.5 h-3.5" />
            <span>Bangladeshi SME Regulatory Intelligence MVP</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
            Automated Regulatory Audit & <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-pink-400 bg-clip-text text-transparent">Action Plan Generator</span>
          </h1>

          <p className="text-lg text-slate-300 leading-relaxed font-normal">
            Upload your company's internal SOP document. ComplianceOS deploys a 5-agent RAG pipeline to detect regulatory changes, evaluate gap risk, rewrite redlined policy drafts, and generate verified technical fixes with exact citations back to legal clauses.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              href="/upload"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-lg shadow-indigo-600/30 hover:shadow-indigo-500/40 transition-all group"
            >
              <UploadCloud className="w-5 h-5" />
              <span>Upload SOP & Start Analysis</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link
              href="/regulations"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700 font-semibold transition-all"
            >
              <FileText className="w-5 h-5 text-indigo-400" />
              <span>Inspect Regulation Diff</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Legal Disclaimer */}
      <LegalDisclaimer />

      {/* Feature Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Watcher Alert Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all flex flex-col justify-between">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white">1. Watcher Agent</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Monitors regulatory updates (NBR VAT SRO 2025). Computes cryptographic text diffs and extracts plain-language obligation changes.
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-slate-800/80 text-xs text-amber-400/90 font-medium flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Diffs `regulation_before.txt` vs `after.txt`</span>
          </div>
        </div>

        {/* Multi-Agent RAG Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all flex flex-col justify-between">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Cpu className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white">2. Multi-Agent RAG</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Retriever queries ChromaDB vector embeddings (`all-MiniLM-L6-v2`) to match regulation clauses against internal SOP chunks.
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-slate-800/80 text-xs text-indigo-400 font-medium flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Deterministic vector similarity search</span>
          </div>
        </div>

        {/* Critic & Citation Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all flex flex-col justify-between">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
              <FileCheck className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white">3. Critic Verification</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Critic Agent executes string matching (`rapidfuzz`) to verify citations against source text, computing true mathematical confidence scores.
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-slate-800/80 text-xs text-emerald-400 font-medium flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Computed confidence (never LLM guessed)</span>
          </div>
        </div>

      </div>

      {/* Target Scenario Banner */}
      <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 sm:p-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2">
          <h4 className="text-lg font-bold text-white">Active Fixture Scenario: Bangladeshi NBR VAT SRO 2025</h4>
          <p className="text-sm text-slate-400">
            Mandatory reduction of monthly VAT filing deadline from 30 days to 15 calendar days and mandatory designation of a named VAT Filing Officer.
          </p>
        </div>
        <Link
          href="/analysis"
          className="shrink-0 px-5 py-2.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-sm font-semibold transition-all"
        >
          Launch Agent Pipeline →
        </Link>
      </div>

    </div>
  );
}
