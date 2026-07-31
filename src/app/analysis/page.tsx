'use client';
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Cpu, CheckCircle2, Loader2, ArrowRight, ShieldCheck, Database, FileDiff, Scale, Lock } from 'lucide-react';
import { runAnalysis, createCompanyProfile, uploadDocument } from '@/lib/api';

export default function AnalysisPage() {
  const router = useRouter();

  const [companyProfileId, setCompanyProfileId] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    // Read from session storage if present
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
      desc: 'Diffing regulation fixture texts and generating plain-language summary...',
      icon: FileDiff,
    },
    {
      id: 2,
      name: 'Agent 2 — Retriever',
      desc: 'Querying ChromaDB vector embeddings for top SOP sections (k=3)...',
      icon: Database,
    },
    {
      id: 3,
      name: 'Agent 3 — Impact Analyzer',
      desc: 'Evaluating regulation clauses vs SOP excerpts to detect gaps and conflicts...',
      icon: Scale,
    },
    {
      id: 4,
      name: 'Agent 4 — Action Plan Generator',
      desc: 'Formulating redlined policy text & concrete technical fixes...',
      icon: Cpu,
    },
    {
      id: 5,
      name: 'Agent 5 — Critic / Verifier',
      desc: 'Executing RapidFuzz citation verification & computing mathematical confidence...',
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

      // Auto-initialize sample profile if none uploaded yet
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

      // Step-by-step progress animation across the 5 agents
      for (let s = 1; s <= 5; s++) {
        setActiveStep(s);
        await new Promise((res) => setTimeout(res, 800));
      }

      // Run actual FastAPI analyze endpoint
      const result = await runAnalysis(currentCId, currentDId);

      // Navigate to Action Plan deliverable page
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
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold">
          <Cpu className="w-3.5 h-3.5" />
          <span>Synchronous 5-Agent RAG Orchestration</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Compliance Analysis Launchpad
        </h1>
        <p className="text-sm text-slate-400">
          Execute the multi-agent pipeline to compare your company SOP against the NBR VAT regulatory change. Target completion &lt; 30 seconds.
        </p>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs text-center font-medium">
          {errorMsg}
        </div>
      )}

      {/* Main Execution Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-8 space-y-8 shadow-2xl backdrop-blur-md">
        
        {/* Active Pipeline List */}
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
                    ? 'bg-indigo-950/40 border-indigo-500/50 shadow-lg shadow-indigo-500/10'
                    : isDone
                    ? 'bg-slate-950/60 border-slate-800/80'
                    : 'bg-slate-950/30 border-slate-900 opacity-60'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 ${
                      isCurrent
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                        : isDone
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-800 text-slate-500'
                    }`}
                  >
                    {isDone ? <CheckCircle2 className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{agent.name}</span>
                      {isCurrent && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase tracking-wider font-mono">
                          Running
                        </span>
                      )}
                    </h4>
                    <p className="text-xs text-slate-400 mt-0.5">{agent.desc}</p>
                  </div>
                </div>

                {isCurrent && <Loader2 className="w-5 h-5 animate-spin text-indigo-400 shrink-0" />}
              </div>
            );
          })}
        </div>

        {/* Action Button */}
        <div>
          <button
            onClick={handleStartPipeline}
            disabled={running}
            className="w-full py-4 px-6 rounded-2xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white font-bold text-base shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-3 transition-all"
          >
            {running ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Running 5-Agent RAG Pipeline...</span>
              </>
            ) : (
              <>
                <span>Run 5-Agent Compliance Analysis</span>
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </div>

      </div>

    </div>
  );
}
