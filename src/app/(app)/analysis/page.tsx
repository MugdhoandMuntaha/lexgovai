'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Cpu, CheckCircle2, Loader2, ArrowRight, ShieldCheck, Database, FileDiff, Scale, XCircle, FileText } from 'lucide-react';
import { streamAnalysis, createCompanyProfile, uploadSampleDocument } from '@/lib/api';
import { loadWorkspace, saveWorkspace, Workspace } from '@/lib/session';
import { PipelineEvent, ApiError } from '@/lib/types';
import { useAuth } from '@/context/AuthContext';
import { PlanBadge } from '@/components/PlanBadge';

type AgentStatus = 'pending' | 'running' | 'done' | 'failed';

interface AgentState {
  status: AgentStatus;
  detail?: string;
  durationMs?: number;
}

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

const initialStates = (): Record<number, AgentState> =>
  Object.fromEntries(agents.map((a) => [a.id, { status: 'pending' as AgentStatus }]));

export default function AnalysisPage() {
  const router = useRouter();
  const { subscription, limits, openUpgradeModal } = useAuth();

  const [workspace, setWorkspace] = useState<Workspace | null>(() => {
    if (typeof window === 'undefined') return null;
    return loadWorkspace();
  });
  const [running, setRunning] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [states, setStates] = useState<Record<number, AgentState>>(initialStates);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [totalMs, setTotalMs] = useState<number | null>(null);

  const updateAgent = (id: number, patch: AgentState) => setStates((prev) => ({ ...prev, [id]: patch }));

  const handleEvent = (event: PipelineEvent) => {
    switch (event.type) {
      case 'agent_started':
        updateAgent(event.agent, { status: 'running' });
        break;
      case 'agent_completed':
        updateAgent(event.agent, { status: 'done', detail: event.detail, durationMs: event.duration_ms });
        break;
      case 'error':
        if (event.agent) updateAgent(event.agent, { status: 'failed', detail: event.message });
        break;
      case 'completed':
        setTotalMs(event.duration_ms);
        break;
    }
  };

  /** No SOP uploaded in this session: index the bundled sample SOP so the pipeline has something to analyse. */
  const ensureWorkspace = async (): Promise<Workspace> => {
    if (workspace) return workspace;
    setPreparing(true);
    try {
      const companyName = 'Apex Logistics Bangladesh Ltd.';
      const profile = await createCompanyProfile({
        company_name: companyName,
        industry: 'Logistics & Freight Services',
        country: 'Bangladesh',
        description: 'Dhaka-based freight forwarding and trade logistics SME.',
      });
      const doc = await uploadSampleDocument(profile.id);
      const ws: Workspace = {
        companyProfileId: profile.id,
        companyName,
        documentId: doc.document_id,
        documentName: doc.filename,
        sections: doc.sections,
      };
      saveWorkspace(ws);
      setWorkspace(ws);
      return ws;
    } finally {
      setPreparing(false);
    }
  };

  const handleStartPipeline = async () => {
    setRunning(true);
    setErrorMsg(null);
    setTotalMs(null);
    setStates(initialStates());

    try {
      const ws = await ensureWorkspace();
      const plan = await streamAnalysis(ws.companyProfileId, ws.documentId, handleEvent, ws.regulationId);
      router.push(`/action-plan/${plan.id}`);
    } catch (err: unknown) {
      console.error(err);
      if (err instanceof ApiError && (err.status === 403 || err.status === 429)) {
        openUpgradeModal(
          err.code === 'QUOTA_EXCEEDED' ? 'Detailed Analyses Quota' : (err.capability || 'Impact Analysis'),
          err.upgrade_to || err.required_plan || 'starter',
        );
      }
      setErrorMsg(err instanceof Error ? err.message : 'Pipeline execution failed.');
      setRunning(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      
      {/* Header */}
      <div className="text-center space-y-3 max-w-2xl mx-auto">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold uppercase tracking-wider">
          <Cpu className="w-3.5 h-3.5" />
          <span>Live 5-Agent RAG Execution</span>
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          Compliance Analysis Pipeline
        </h1>
        <p className="text-sm text-slate-500">
          Execute multi-agent benchmarking against NBR VAT regulations. Progress below is streamed live from the backend as each agent finishes.
        </p>
      </div>

      {/* Target document */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3 text-xs shadow-2xs">
        <div className="flex items-center gap-2 text-slate-700">
          <FileText className="w-4 h-4 text-emerald-600" />
          {workspace ? (
            <div className="space-y-0.5">
              <div>
                Analyzing <strong className="text-slate-900">{workspace.documentName}</strong> for{' '}
                <strong className="text-slate-900">{workspace.companyName}</strong> ({workspace.sections.length} sections indexed)
              </div>
              <div className="text-[11px] text-emerald-700 font-medium">
                Target Regulation: <strong>{workspace.regulationTitle || 'NBR VAT SRO Clause 4.2'}</strong>
              </div>
            </div>
          ) : (
            <span>No SOP uploaded in this session. The bundled sample SOP (Apex Logistics) will be indexed and analyzed.</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {subscription && <PlanBadge planId={subscription.plan_id} size="sm" />}
          {limits?.detailed_analyses !== undefined && (
            <span className="font-mono text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-full">
              Cap: {limits.detailed_analyses}/mo
            </span>
          )}
          <Link href="/upload" className="font-semibold text-emerald-700 hover:text-emerald-800 ml-2">
            {workspace ? 'Upload a different SOP' : 'Upload your own SOP'}
          </Link>
        </div>
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
            const state = states[agent.id];
            const isDone = state.status === 'done';
            const isCurrent = state.status === 'running';
            const isFailed = state.status === 'failed';

            return (
              <div
                key={agent.id}
                className={`p-4 rounded-2xl border transition-all flex items-center justify-between gap-4 ${
                  isFailed
                    ? 'bg-rose-50/60 border-rose-300'
                    : isCurrent
                    ? 'bg-emerald-50/60 border-emerald-300 shadow-2xs'
                    : isDone
                    ? 'bg-slate-50/80 border-slate-200'
                    : 'bg-slate-50/30 border-slate-100 opacity-60'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                      isFailed
                        ? 'bg-rose-100 text-rose-700 border border-rose-200'
                        : isCurrent
                        ? 'bg-emerald-600 text-white shadow-2xs'
                        : isDone
                        ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                        : 'bg-slate-200 text-slate-500'
                    }`}
                  >
                    {isFailed ? <XCircle className="w-4 h-4" /> : isDone ? <CheckCircle2 className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
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
                    <p className={`text-xs mt-0.5 ${isFailed ? 'text-rose-700' : isDone ? 'text-slate-700' : 'text-slate-500'}`}>
                      {state.detail ?? agent.desc}
                    </p>
                  </div>
                </div>

                {isCurrent && <Loader2 className="w-4 h-4 animate-spin text-emerald-600 shrink-0" />}
                {isDone && state.durationMs !== undefined && (
                  <span className="text-[11px] font-mono text-slate-400 shrink-0">{(state.durationMs / 1000).toFixed(1)}s</span>
                )}
              </div>
            );
          })}
        </div>

        {totalMs !== null && (
          <p className="text-center text-xs font-semibold text-emerald-700">
            Pipeline completed in {(totalMs / 1000).toFixed(1)}s. Opening the action plan...
          </p>
        )}

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
                <span>{preparing ? 'Indexing sample SOP...' : 'Executing Multi-Agent RAG Pipeline...'}</span>
              </>
            ) : (
              <>
                <span>{errorMsg ? 'Retry Compliance Pipeline' : 'Run Compliance Pipeline'}</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>

      </div>

    </div>
  );
}
