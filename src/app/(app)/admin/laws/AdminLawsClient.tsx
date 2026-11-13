'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Play,
  Upload,
  Globe,
  Clock,
  ArrowLeft,
  ExternalLink,
  AlertTriangle,
} from 'lucide-react';
import { LawSourceItem, LawItem, LawVersionItem, LawCoverageResponse } from '@/lib/types';
import {
  approveLaw,
  rejectLaw,
  updateAdminLawSource,
  triggerLawIngestRun,
  uploadLawDocument,
} from '@/lib/api';

interface AdminLawsClientProps {
  initialQueue: Array<{
    queue_id: string;
    law_id: string;
    reason: string;
    created_at: string;
    law: LawItem;
    version?: LawVersionItem | null;
  }>;
  initialSources: LawSourceItem[];
  coverage: LawCoverageResponse | null;
}

export function AdminLawsClient({
  initialQueue,
  initialSources,
  coverage,
}: AdminLawsClientProps) {
  const [activeTab, setActiveTab] = useState<'queue' | 'sources' | 'upload'>('queue');
  const [queue, setQueue] = useState(initialQueue);
  const [sources, setSources] = useState(initialSources);

  // Action status states
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const [statusMessage, setStatusMessage] = useState<{ text: string; isError?: boolean } | null>(null);

  // Manual upload form states
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitleEn, setUploadTitleEn] = useState('');
  const [uploadTitleBn, setUploadTitleBn] = useState('');
  const [uploadIssuingBody, setUploadIssuingBody] = useState('National Board of Revenue');
  const [uploadLawType, setUploadLawType] = useState('act');
  const [uploadYear, setUploadYear] = useState('2024');
  const [isUploading, setIsUploading] = useState(false);

  const handleApprove = async (lawId: string) => {
    setActionLoading((prev) => ({ ...prev, [lawId]: true }));
    setStatusMessage(null);
    try {
      await approveLaw(lawId);
      setQueue((prev) => prev.filter((item) => item.law_id !== lawId));
      setStatusMessage({ text: `Law ${lawId} approved and published to the library.` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Approval failed.';
      setStatusMessage({ text: msg, isError: true });
    } finally {
      setActionLoading((prev) => ({ ...prev, [lawId]: false }));
    }
  };

  const handleReject = async (lawId: string) => {
    const reason = prompt('Please enter the rejection reason (e.g. illegible scan, duplicate, incomplete text):');
    if (!reason) return;

    setActionLoading((prev) => ({ ...prev, [lawId]: true }));
    setStatusMessage(null);
    try {
      await rejectLaw(lawId, reason);
      setQueue((prev) => prev.filter((item) => item.law_id !== lawId));
      setStatusMessage({ text: `Law ${lawId} rejected and moved to rejected state.` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Rejection failed.';
      setStatusMessage({ text: msg, isError: true });
    } finally {
      setActionLoading((prev) => ({ ...prev, [lawId]: false }));
    }
  };

  const handleToggleSource = async (source: LawSourceItem) => {
    const nextState = !source.enabled;
    setActionLoading((prev) => ({ ...prev, [source.id]: true }));
    setStatusMessage(null);
    try {
      await updateAdminLawSource(source.id, { enabled: nextState });
      setSources((prev) =>
        prev.map((s) => (s.id === source.id ? { ...s, enabled: nextState } : s))
      );
      setStatusMessage({
        text: `Source "${source.name}" ${nextState ? 'enabled' : 'disabled'}.`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to toggle source.';
      setStatusMessage({ text: msg, isError: true });
    } finally {
      setActionLoading((prev) => ({ ...prev, [source.id]: false }));
    }
  };

  const handleTriggerIngest = async (sourceId?: string) => {
    setStatusMessage(null);
    try {
      const res = await triggerLawIngestRun(sourceId);
      setStatusMessage({ text: `Ingestion job triggered! Job ID: ${res.job_id}` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to trigger ingestion.';
      setStatusMessage({ text: msg, isError: true });
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      alert('Please select a PDF or text file.');
      return;
    }
    setIsUploading(true);
    setStatusMessage(null);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('canonical_title_en', uploadTitleEn);
      if (uploadTitleBn) formData.append('canonical_title_bn', uploadTitleBn);
      formData.append('issuing_body', uploadIssuingBody);
      formData.append('law_type', uploadLawType);
      if (uploadYear) formData.append('year', uploadYear);

      const res = await uploadLawDocument(formData);
      setStatusMessage({
        text: `Document uploaded! Law ID: ${res.law_id}. Publish state: ${res.publish_state}${
          res.ocr_quality !== undefined && res.ocr_quality !== null
            ? ` (OCR quality: ${(res.ocr_quality * 100).toFixed(0)}%)`
            : ''
        }`,
      });
      setUploadFile(null);
      setUploadTitleEn('');
      setUploadTitleBn('');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed.';
      setStatusMessage({ text: msg, isError: true });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-8 py-4">
      {/* Back button & Admin Header */}
      <div className="flex items-center justify-between">
        <Link
          href="/admin"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Platform Admin</span>
        </Link>

        <Link
          href="/laws"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-semibold transition-colors"
        >
          <span>View Public Legal Library</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Main Admin Hero */}
      <div className="p-6 sm:p-8 rounded-3xl bg-slate-900 text-white space-y-3 shadow-sm">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-semibold uppercase tracking-wider">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Legal Library Administration & Critic Queue</span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
          Bangladesh Law Curation & Pipeline Control
        </h1>

        <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
          Manage AI extraction review queue, configure government web crawler sources, and manually ingest regulatory gazettes. Currently {coverage?.published_laws_count ?? 0} enactments live.
        </p>
      </div>

      {/* Status banner */}
      {statusMessage && (
        <div
          className={`p-4 rounded-2xl text-xs font-medium flex items-center justify-between shadow-2xs ${
            statusMessage.isError
              ? 'bg-rose-50 border border-rose-200 text-rose-800'
              : 'bg-emerald-50 border border-emerald-200 text-emerald-800'
          }`}
        >
          <span>{statusMessage.text}</span>
          <button
            type="button"
            onClick={() => setStatusMessage(null)}
            className="text-[11px] font-bold underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-6 text-xs font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab('queue')}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 -mb-px ${
            activeTab === 'queue'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Review Queue</span>
          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-mono">
            {queue.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('sources')}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 -mb-px ${
            activeTab === 'sources'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Globe className="w-4 h-4" />
          <span>Government Sources</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-mono">
            {sources.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('upload')}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 -mb-px ${
            activeTab === 'upload'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Upload className="w-4 h-4" />
          <span>Manual Document Ingestion</span>
        </button>
      </div>

      {/* Tab 1: Review Queue */}
      {activeTab === 'queue' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">
              Pending Human Verification Queue
            </h2>
            <span className="text-xs text-slate-500">
              Auto-publishing policy routes low-confidence OCR or critic score mismatches here.
            </span>
          </div>

          {queue.length === 0 ? (
            <div className="p-12 text-center rounded-2xl bg-white border border-slate-200">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
              <h3 className="text-sm font-bold text-slate-900">Review queue is empty</h3>
              <p className="text-xs text-slate-500 mt-1">
                All discovered and ingested laws met the critic verification thresholds or have already been reviewed.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {queue.map((item) => {
                const isLoading = actionLoading[item.law_id] ?? false;

                return (
                  <div
                    key={item.queue_id}
                    className="p-5 rounded-2xl bg-white border border-amber-200/90 shadow-2xs space-y-4"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-[10px] font-bold uppercase tracking-wider">
                            Pending Review
                          </span>
                          <span className="text-[11px] font-mono text-slate-500">
                            Law ID: {item.law_id}
                          </span>
                          <span className="text-[11px] text-slate-500">
                            Queued: {item.created_at.slice(0, 16).replace('T', ' ')}
                          </span>
                        </div>

                        <h3 className="text-base font-bold text-slate-900">
                          {item.law.canonical_title_en}
                        </h3>

                        {item.law.canonical_title_bn && (
                          <p className="text-xs text-slate-500 font-sans">
                            {item.law.canonical_title_bn}
                          </p>
                        )}
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          disabled={isLoading}
                          onClick={() => handleReject(item.law_id)}
                          className="px-3.5 py-1.5 rounded-xl border border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Reject</span>
                        </button>

                        <button
                          type="button"
                          disabled={isLoading}
                          onClick={() => handleApprove(item.law_id)}
                          className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-2xs"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Approve & Publish</span>
                        </button>
                      </div>
                    </div>

                    {/* Reason Callout */}
                    <div className="p-3.5 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-amber-900 space-y-1">
                      <div className="flex items-center gap-1.5 font-bold text-[11px] uppercase tracking-wider text-amber-800">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                        <span>Flagged Reason:</span>
                      </div>
                      <p className="leading-relaxed">{item.reason}</p>
                    </div>

                    {/* AI Summary Preview */}
                    {item.law.summary_ai && (
                      <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                          Extracted AI Summary Preview:
                        </span>
                        <p className="text-slate-700 leading-relaxed">
                          {item.law.summary_ai}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Sources Management */}
      {activeTab === 'sources' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">
              Government Law Portals & Feeds
            </h2>

            <button
              type="button"
              onClick={() => handleTriggerIngest()}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-2xs"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Trigger Routine Discovery Run (All Enabled)</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sources.map((s) => {
              const isLoading = actionLoading[s.id] ?? false;

              return (
                <div
                  key={s.id}
                  className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">{s.name}</h3>
                      <a
                        href={s.base_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-indigo-600 hover:underline flex items-center gap-1 mt-0.5"
                      >
                        <span>{s.base_url}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>

                    <button
                      type="button"
                      disabled={isLoading}
                      onClick={() => handleToggleSource(s)}
                      className={`px-3 py-1 rounded-full text-xs font-bold transition-all ${
                        s.enabled
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                          : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
                      }`}
                    >
                      {s.enabled ? 'Enabled' : 'Disabled'}
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600 pt-2 border-t border-slate-100">
                    <div>
                      <span className="text-slate-400">Source Type:</span>{' '}
                      <span className="font-mono font-medium">{s.source_type}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Rate Limit:</span>{' '}
                      <span className="font-mono font-medium">{s.rate_limit}s delay</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Last Status:</span>{' '}
                      <span className="font-mono font-medium capitalize">{s.last_status || 'idle'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Last Crawled:</span>{' '}
                      <span className="font-mono font-medium">
                        {s.last_run_at ? s.last_run_at.slice(0, 10) : 'Never'}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 flex justify-end">
                    <button
                      type="button"
                      disabled={!s.enabled || isLoading}
                      onClick={() => handleTriggerIngest(s.id)}
                      className="px-3 py-1.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-50 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      <Play className="w-3 h-3" />
                      <span>Ingest Now</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 3: Manual Ingestion */}
      {activeTab === 'upload' && (
        <div className="max-w-xl mx-auto p-6 sm:p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-6">
          <div className="space-y-1.5">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Upload className="w-4 h-4 text-indigo-600" />
              <span>Manual Law Document Ingestion</span>
            </h2>
            <p className="text-xs text-slate-500 leading-relaxed">
              Upload an official gazette PDF (digital text or scanned) or plain text document. It will be passed through the full Extraction (pypdf/OCR) &rarr; Structuring &rarr; Classification &rarr; RapidFuzz Critic pipeline.
            </p>
          </div>

          <form onSubmit={handleUploadSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Gazette PDF or Text File (.pdf, .txt)
              </label>
              <input
                type="file"
                accept=".pdf,.txt"
                required
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Canonical Title (English) *
              </label>
              <input
                type="text"
                required
                value={uploadTitleEn}
                onChange={(e) => setUploadTitleEn(e.target.value)}
                placeholder="e.g. Value Added Tax and Supplementary Duty Act, 2012"
                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:border-indigo-400"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Canonical Title (Bengali)
              </label>
              <input
                type="text"
                value={uploadTitleBn}
                onChange={(e) => setUploadTitleBn(e.target.value)}
                placeholder="e.g. মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২"
                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:border-indigo-400 font-sans"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Issuing Government Body
                </label>
                <input
                  type="text"
                  required
                  value={uploadIssuingBody}
                  onChange={(e) => setUploadIssuingBody(e.target.value)}
                  placeholder="e.g. National Board of Revenue"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:border-indigo-400"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Enactment Type
                </label>
                <select
                  value={uploadLawType}
                  onChange={(e) => setUploadLawType(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs focus:outline-none focus:border-indigo-400"
                >
                  <option value="act">Act</option>
                  <option value="ordinance">Ordinance</option>
                  <option value="sro">SRO</option>
                  <option value="rule">Rule</option>
                  <option value="circular">Circular</option>
                  <option value="order">Order</option>
                  <option value="gazette_notice">Gazette Notice</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Year of Enactment
              </label>
              <input
                type="number"
                value={uploadYear}
                onChange={(e) => setUploadYear(e.target.value)}
                placeholder="2024"
                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:border-indigo-400"
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isUploading}
                className="w-full py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-colors shadow-2xs"
              >
                <Upload className="w-4 h-4" />
                <span>{isUploading ? 'Extracting & Structuring Document...' : 'Ingest Document into Library'}</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
