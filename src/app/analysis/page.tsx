'use client';
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Cpu, CheckCircle2, Loader2, ArrowRight, ShieldCheck, Database, FileDiff, Scale } from 'lucide-react';
import { runAnalysis, createCompanyProfile, uploadDocument } from '@/lib/api';

export default function AnalysisPage() {
  const router = useRouter();

  const [companyProfileId, setCompanyProfileId] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const cId = sessionStorage.getItem('company_profile_id');
    const dId = sessionStorage.getItem('document_id');
    if (cId && dId) {
      setCompanyProfileId(cId);
      setDocumentId(dId);
    }
  }, []);

  const agents = [
    {
      id: 1,
      name: 'Agent 1 — Watcher',
      desc: 'Diffing regulation text pair and extracting key legal obligations...',
      icon: FileDiff,
    },
    {
      id: 2,
      name: 'Agent 2 — Retriever',
      desc: 'Searching ChromaDB vector embeddings for top-k relevant SOP sections...',
      icon: Database,
    },
    {
      id: 3,
      name: 'Agent 3 — Impact Analyzer',
      desc: 'Analyzing regulatory clauses against SOP rules to detect compliance gaps...',
      icon: Scale,
    },
    {
      id: 4,
      name: 'Agent 4 — Action Plan Generator',
      desc: 'Drafting policy redline amendments and technical engineering fixes...',
      icon: Cpu,
    },
    {
      id: 5,
      name: 'Agent 5 — Critic / Verifier',
      desc: 'Executing RapidFuzz citation verification & calculating mathematical confidence...',
      icon: ShieldCheck,
    },
  ];

  const handleStartPipeline = async () => {
    setRunning(true);
    setErrorMsg(null);
    setActiveStep(1);

    try {
      let currentCId = companyProfileId;
      let currentDId = documentId;

      if (!currentCId || !currentDId) {
        setActiveStep(1);
        const profile = await createCompanyProfile({
          company_name: 'Apex Logistics Bangladesh Ltd.',
          industry: 'Logistics & Freight Services',
          country: 'Bangladesh',
          description: 'Dhaka-based freight forwarding and trade logistics SME.',
        });

        const sampleText = `Standard Operating Procedure: Financial Operations & Compliance (SOP-FIN-2024-v2)
Company: Apex Logistics Bangladesh Ltd.

Section 1: Overview and Purpose
This document governs routine tax, VAT, and accounting procedures.

Section 6.1: VAT Submission Timelines & Responsibilities
The finance and accounts department submits monthly VAT returns to the NBR within 30 calendar days following the tax month end. Any available finance team member is authorized to process filings via the NBR online portal.`;

        const blob = new Blob([sampleText], { type: 'text/plain' });
        const file = new File([blob], 'Apex_Logistics_SOP.txt', { type: 'text/plain' });
        const docRes = await uploadDocument(profile.id, file);

        currentCId = profile.id;
        currentDId = docRes.document_id;
        setCompanyProfileId(currentCId);
        setDocumentId(currentDId);
      }

      for (let s = 1; s <= 5; s++) {
        setActiveStep(s);
        await new Promise((res) => setTimeout(res, 750));
      }

      const result = await runAnalysis(currentCId, currentDId);

      router.push(`/action-plan/${result.id}`);

    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'Pipeline execution failed.');
      setRunning(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      
      {/* Header */}
      <div className="text-center space-y-3 max-w-2xl mx-auto">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold uppercase tracking-wider">
          <Cpu className="w-3.5 h-3.5" />
          <span>Synchronous 5-Agent RAG Execution</span>
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          Compliance Analysis Pipeline
        </h1>
        <p className="text-sm text-slate-500">
          Execute multi-agent benchmarking against NBR VAT regulations. Total pipeline execution target &lt; 30 seconds.
        </p>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs text-center font-medium">
          {errorMsg}
        </div>
      )}

      {/* Main Card */}
      <div className="bg-white border border-slate-200/90 rounded-3xl p-8 space-y-8 shadow-2xs">
        
        {/* Agent Step List */}
        <div className="space-y-4">
          {agents.map((agent) => {
            const Icon = agent.icon;
            const isDone = activeStep > agent.id;
            const isCurrent = activeStep === agent.id;

            return (
              <div
                key={agent.id}
                className={`p-4 rounded-2xl border transition-all flex items-center justify-between gap-4 ${
                  isCurrent
                    ? 'bg-emerald-50/60 border-emerald-300 shadow-2xs'
                    : isDone
                    ? 'bg-slate-50/80 border-slate-200'
                    : 'bg-slate-50/30 border-slate-100 opacity-60'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                      isCurrent
                        ? 'bg-emerald-600 text-white shadow-2xs'
                        : isDone
                        ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                        : 'bg-slate-200 text-slate-500'
                    }`}
                  >
                    {isDone ? <CheckCircle2 className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <span>{agent.name}</span>
                      {isCurrent && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 uppercase tracking-wider font-mono font-semibold">
                          Processing
                        </span>
                      )}
                    </h4>
                    <p className="text-xs text-slate-500 mt-0.5">{agent.desc}</p>
                  </div>
                </div>

                {isCurrent && <Loader2 className="w-4 h-4 animate-spin text-emerald-600 shrink-0" />}
              </div>
            );
          })}
        </div>

        {/* Action Button */}
        <div>
          <button
            onClick={handleStartPipeline}
            disabled={running}
            className="w-full py-4 px-6 rounded-2xl bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-sm shadow-sm flex items-center justify-center gap-2 transition-all"
          >
            {running ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Executing Multi-Agent RAG Pipeline...</span>
              </>
            ) : (
              <>
                <span>Run Compliance Pipeline</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>

      </div>

    </div>
  );
}
