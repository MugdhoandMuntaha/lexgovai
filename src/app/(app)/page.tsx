'use client';
import React from 'react';
import Link from 'next/link';
import { Shield, FileCheck2, ArrowRight, FileText, Scale, Lock, BookOpen, Sparkles } from 'lucide-react';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

export default function Home() {
  return (
    <div className="space-y-12 py-4">
      
      {/* Minimal Aesthetic Hero Section */}
      <section className="relative overflow-hidden rounded-3xl bg-white border border-slate-200/90 p-8 sm:p-12 shadow-sm">
        <div className="max-w-3xl space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold uppercase tracking-wider">
            <Lock className="w-3.5 h-3.5" />
            <span>Enterprise Multi-Agent RAG Engine</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
            Automated Regulatory Compliance & SOP Impact Analysis
          </h1>

          <p className="text-base text-slate-600 leading-relaxed">
            Instantly benchmark your company standard operating procedures (SOPs) against National Board of Revenue (NBR) regulatory changes. Detect compliance gaps, compute mathematical evidence scores, and draft audit-ready policy revisions.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              href="/upload"
              className="px-6 py-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm shadow-sm flex items-center gap-2 transition-all"
            >
              <span>Launch Ingestion & Analysis</span>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              href="/regulations"
              className="px-6 py-3.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 font-semibold text-sm transition-all flex items-center gap-2"
            >
              <FileText className="w-4 h-4 text-emerald-600" />
              <span>View Regulation Text Diff</span>
            </Link>

            <Link
              href="/laws"
              className="px-6 py-3.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-semibold text-sm transition-all flex items-center gap-2"
            >
              <BookOpen className="w-4 h-4 text-indigo-600" />
              <span>Bangladesh Legal Library</span>
            </Link>
          </div>
        </div>
      </section>

      {/* Bangladesh Legal Library Spotlight */}
      <section className="p-6 sm:p-8 rounded-3xl bg-linear-to-r from-slate-900 via-indigo-950 to-slate-900 text-white border border-indigo-900/50 shadow-md flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5" />
            <span>NEW: Authoritative Statutory Repository</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight">
            Explore Bangladesh Laws & Gazette Enactments
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            Access acts, ordinances, SROs, and circulars directly from official government sources. Search in English or Bengali, run clause-level redline diffs across editions, and benchmark your SOPs directly against enacted law.
          </p>
        </div>

        <Link
          href="/laws"
          className="px-6 py-3.5 rounded-2xl bg-white hover:bg-slate-100 text-slate-900 font-bold text-xs uppercase tracking-wider transition-all shrink-0 flex items-center gap-2 shadow-sm"
        >
          <span>Browse Legal Library</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </section>

      {/* Core Enterprise Architecture Grid */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        <div className="p-6 rounded-2xl bg-white border border-slate-200/90 shadow-2xs space-y-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 font-bold">
            <Shield className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-900">Cryptographic Regulatory Watcher</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Agent 1 diffs regulatory amendments, extracting explicit obligations, deadline changes, and non-compliance penalty thresholds.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200/90 shadow-2xs space-y-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 font-bold">
            <Scale className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-900">Multi-Agent Vector RAG</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Agents 2 & 3 perform top-k vector searches across ChromaDB embeddings to identify conflicts between SOP rules and new legal requirements.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white border border-slate-200/90 shadow-2xs space-y-3">
          <div className="w-10 h-10 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-600 font-bold">
            <FileCheck2 className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-900">Deterministic Critic Verification</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Agent 5 validates string citations using RapidFuzz string matching, generating exact mathematical confidence scores and review flags.
          </p>
        </div>

      </section>

      {/* 5-Agent RAG Process Workflow */}
      <section className="bg-white border border-slate-200/90 rounded-3xl p-8 space-y-6 shadow-2xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Multi-Agent Intelligence Workflow</h2>
            <p className="text-xs text-slate-500 mt-0.5">Automated synchronous pipeline execution target &lt; 30 seconds</p>
          </div>
          <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            5 ACTIVE AGENTS
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {[
            { step: '01', name: 'Watcher', task: 'Diff Regulation Text' },
            { step: '02', name: 'Retriever', task: 'Query SOP Embeddings' },
            { step: '03', name: 'Impact Analyzer', task: 'Detect Gaps & Risks' },
            { step: '04', name: 'Generator', task: 'Draft Policy Redlines' },
            { step: '05', name: 'Critic / Verifier', task: 'Verify Citations & Math' },
          ].map((item, idx) => (
            <div key={idx} className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
              <div className="text-[10px] font-mono font-bold text-emerald-600 uppercase tracking-widest">Agent {item.step}</div>
              <div className="text-sm font-bold text-slate-900">{item.name}</div>
              <div className="text-xs text-slate-500">{item.task}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Subscription Pricing Banner */}
      <section className="bg-gradient-to-r from-indigo-900 to-slate-900 rounded-3xl p-8 sm:p-10 text-white shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">
              Subscription Plans & Metering
            </span>
            <h2 className="text-2xl font-bold tracking-tight text-white">
              Transparent Compliance Pricing for Any Enterprise Stage
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Start free with our 9-step guided questionnaire, or upgrade to Starter (৳999/mo) and Growth (৳2,999/mo) for full SOP document indexing and multi-agent RAG impact analysis.
            </p>
          </div>
          <Link
            href="/pricing"
            className="px-6 py-3 rounded-xl bg-white text-slate-900 font-bold text-xs hover:bg-slate-100 transition-all shrink-0 flex items-center gap-2 shadow-sm"
          >
            <span>Compare Plans & Pricing</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Legal Notice Footer */}
      <LegalDisclaimer />

    </div>
  );
}
