'use client';
import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { UploadCloud, FileText, CheckCircle2, ArrowRight, Building, Globe, Shield, RefreshCw, Sparkles, Scale } from 'lucide-react';
import { createCompanyProfile, uploadDocument, uploadSampleDocument } from '@/lib/api';
import { saveWorkspace } from '@/lib/session';
import { DocumentUploadResponse, ApiError } from '@/lib/types';
import { StartFreshWizard } from '@/components/StartFreshWizard';
import { useAuth } from '@/context/AuthContext';
import { FeatureGate } from '@/components/FeatureGate';

const regulationsCatalog = [
  { id: 'nbr-vat-sro-4.2', title: 'NBR VAT SRO Clause 4.2 (Value Added Tax)', sector: 'Logistics / Trade' },
  { id: 'bangladesh-labor-act-2023', title: 'Bangladesh Labor Act (Amendment 2023)', sector: 'Human Resources / Manufacturing' },
  { id: 'income-tax-act-2023', title: 'Bangladesh Income Tax Act 2023 (Digital Disallowance)', sector: 'Finance / Corporate' },
];

function UploadContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { openUpgradeModal } = useAuth();

  const paramRegulation = searchParams.get('regulation') || 'nbr-vat-sro-4.2';

  const [mode, setMode] = useState<'upload' | 'start_fresh'>('upload');
  const [selectedRegulation, setSelectedRegulation] = useState<string>(paramRegulation);
  const [companyName, setCompanyName] = useState('Apex Logistics Bangladesh Ltd.');
  const [industry, setIndustry] = useState('Logistics & Freight Services');
  const [country, setCountry] = useState('Bangladesh');

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const finishIngestion = (companyId: string, doc: DocumentUploadResponse) => {
    const regObj = regulationsCatalog.find((r) => r.id === selectedRegulation) || regulationsCatalog[0];
    saveWorkspace({
      companyProfileId: companyId,
      companyName,
      documentId: doc.document_id,
      documentName: doc.filename,
      sections: doc.sections,
      regulationId: regObj.id,
      regulationTitle: regObj.title,
    });
    setSuccessMsg(
      `"${doc.filename}" indexed into ChromaDB: ${doc.chunk_count} chunks across ${doc.sections.length} sections. Benchmark law: ${regObj.title}. Opening pipeline...`,
    );
    setTimeout(() => router.push('/analysis'), 1500);
  };

  const handleUsePresetSample = async () => {
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const profile = await createCompanyProfile({
        company_name: companyName,
        industry: industry,
        country: country,
        description: 'Dhaka-based freight forwarding and trade logistics SME.',
      });
      const doc = await uploadSampleDocument(profile.id);
      finishIngestion(profile.id, doc);
    } catch (err: unknown) {
      console.error(err);
      if (err instanceof ApiError && (err.status === 403 || err.status === 429)) {
        openUpgradeModal(err.capability || 'SOP Ingestion', err.required_plan || err.upgrade_to || 'starter');
      }
      setError(err instanceof Error ? err.message : 'Failed to ingest sample document.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please choose a PDF or TXT file to upload.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const profile = await createCompanyProfile({
        company_name: companyName,
        industry: industry,
        country: country,
        description: `Ingested ${selectedFile.name} on ${new Date().toLocaleDateString()}`,
      });

      const doc = await uploadDocument(profile.id, selectedFile);
      finishIngestion(profile.id, doc);
    } catch (err: unknown) {
      console.error(err);
      if (err instanceof ApiError && (err.status === 403 || err.status === 429)) {
        openUpgradeModal(err.capability || 'SOP Upload', err.required_plan || err.upgrade_to || 'starter');
      }
      setError(err instanceof Error ? err.message : 'Failed to complete document ingestion.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-700">
          <Shield className="w-4 h-4" />
          <span>Ingestion Wizard — Multi-Regulation ChromaDB Indexing</span>
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">SOP Document Ingestion</h1>
        <p className="text-sm text-slate-500">
          Ingest your company Standard Operating Procedures (PDF or TXT) into the vector store for multi-agent compliance benchmarking.
        </p>
      </div>

      {/* Mode Selector Toggle */}
      <div className="flex items-center justify-center">
        <div className="inline-flex p-1.5 rounded-2xl bg-slate-200/70 border border-slate-200 shadow-2xs">
          <button
            type="button"
            onClick={() => setMode('upload')}
            className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              mode === 'upload'
                ? 'bg-white text-slate-900 shadow-2xs border border-slate-200'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileText className="w-4 h-4 text-emerald-600" />
            <span>I have an SOP document</span>
          </button>

          <button
            type="button"
            onClick={() => setMode('start_fresh')}
            className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              mode === 'start_fresh'
                ? 'bg-white text-slate-900 shadow-2xs border border-slate-200'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <span>Start Fresh (No SOP yet)</span>
          </button>
        </div>
      </div>

      {mode === 'start_fresh' ? (
        <StartFreshWizard
          onSOPCreated={(doc) => {
            finishIngestion(doc.company_profile_id, doc);
          }}
        />
      ) : (
        <FeatureGate capability="sop_upload" featureName="SOP Document Upload & Indexing" requiredPlan="starter">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Step 1: Target Regulation & Company Profile */}
            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 space-y-4 shadow-2xs">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                1. Target Statutory Regulation & Company Profile
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Target Regulation Selector */}
                <div className="md:col-span-2">
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Target Statutory Regulation Benchmark
                  </label>
                  <div className="relative">
                    <Scale className="w-4 h-4 text-emerald-600 absolute left-3 top-3" />
                    <select
                      value={selectedRegulation}
                      onChange={(e) => setSelectedRegulation(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2.5 text-xs font-semibold text-slate-900 focus:outline-none focus:border-emerald-500 focus:bg-white"
                    >
                      {regulationsCatalog.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.title} — [{r.sector}]
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Company Legal Name</label>
                  <div className="relative">
                    <Building className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                    <input
                      type="text"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:border-emerald-500 focus:bg-white"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Industry Sector</label>
                  <input
                    type="text"
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:border-emerald-500 focus:bg-white"
                    required
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Jurisdiction</label>
                  <div className="relative">
                    <Globe className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                    <input
                      type="text"
                      value={country}
                      onChange={(e) => setCountry(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:border-emerald-500 focus:bg-white"
                      required
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Step 2: File Upload Zone */}
            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 space-y-4 shadow-2xs">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                  2. Select SOP Document (PDF / TXT)
                </h3>

                <button
                  type="button"
                  onClick={handleUsePresetSample}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-semibold transition-all"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Use Sample SOP (Apex Logistics)</span>
                </button>
              </div>

              <div className="border-2 border-dashed border-slate-200 hover:border-emerald-500/50 rounded-2xl p-8 text-center bg-slate-50/50 transition-colors">
                <input
                  type="file"
                  id="sop-file"
                  accept=".pdf,.txt"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label htmlFor="sop-file" className="cursor-pointer space-y-3 block">
                  <div className="mx-auto w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <UploadCloud className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="text-sm font-bold text-slate-800">
                      {selectedFile ? selectedFile.name : 'Click to select an SOP file'}
                    </span>
                    <p className="text-xs text-slate-400 mt-1">Supports PDF (text extracts) or Plain Text (.txt)</p>
                  </div>
                </label>
              </div>
            </div>

            {error && (
              <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
                {error}
              </div>
            )}

            {successMsg && (
              <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{successMsg}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !selectedFile}
              className="w-full py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-sm shadow-xs transition-all flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Processing & Indexing Vector Embeddings...</span>
                </>
              ) : (
                <>
                  <span>Index SOP & Proceed to Multi-Agent Analysis</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </FeatureGate>
      )}
    </div>
  );
}

export default function UploadPage() {
  return (
    <Suspense fallback={<div className="animate-pulse p-8 text-center text-xs text-slate-400">Loading SOP Ingestion...</div>}>
      <UploadContent />
    </Suspense>
  );
}
