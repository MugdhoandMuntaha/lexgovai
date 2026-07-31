'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { UploadCloud, Building, CheckCircle2, ArrowRight, FileText, Loader2, Sparkles } from 'lucide-react';
import { createCompanyProfile, uploadDocument } from '@/lib/api';

export default function UploadPage() {
  const router = useRouter();
  
  const [companyName, setCompanyName] = useState('Apex Logistics Bangladesh Ltd.');
  const [industry, setIndustry] = useState('Logistics & Freight Services');
  const [description, setDescription] = useState('Leading SME logistics and supply chain service provider based in Dhaka, Bangladesh.');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [loadingStep, setLoadingStep] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<{ companyId: string; documentId: string } | null>(null);

  // Quick 1-click sample creator using default fixture SOP
  const handleUseSampleSOP = () => {
    const sampleText = `Standard Operating Procedure: Financial Operations & Compliance (SOP-FIN-2024-v2)
Company: Apex Logistics Bangladesh Ltd.

Section 1: Overview and Purpose
This document governs the routine financial, tax, and accounting procedures for Apex Logistics Bangladesh Ltd.

Section 4.1: Monthly Ledger Closing
The finance department closes general ledgers by the 10th business day of each calendar month.

Section 6.1: VAT Submission Timelines & Responsibilities
The finance and accounts department submits monthly VAT returns to the NBR within 30 calendar days following the tax month end. Any available finance team member is authorized to submit the electronic filing via the NBR online portal.

Section 6.2: Tax Record Archiving
All VAT chalan forms (Mushak-6.3) and purchase registers (Mushak-6.1) must be preserved in digital format for a period of 5 years.`;

    const blob = new Blob([sampleText], { type: 'text/plain' });
    const file = new File([blob], 'Apex_Logistics_SOP_FIN_2024.txt', { type: 'text/plain' });
    setSelectedFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!selectedFile) {
      setErrorMsg('Please select an SOP document file or click "Use Sample NBR VAT SOP".');
      return;
    }

    try {
      // Step 1: Create Company Profile
      setLoadingStep('Creating Company Profile...');
      const profile = await createCompanyProfile({
        company_name: companyName,
        industry: industry,
        country: 'Bangladesh',
        description: description,
      });

      // Step 2: Upload, Chunk & Embed SOP into ChromaDB
      setLoadingStep('Parsing text, chunking sections & embedding into ChromaDB...');
      const docRes = await uploadDocument(profile.id, selectedFile);

      setSuccessData({
        companyId: profile.id,
        documentId: docRes.document_id,
      });
      setLoadingStep(null);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'An error occurred during upload.');
      setLoadingStep(null);
    }
  };

  const handleProceedToAnalysis = () => {
    if (successData) {
      // Store IDs in session storage for smooth workflow transitions
      sessionStorage.setItem('company_profile_id', successData.companyId);
      sessionStorage.setItem('document_id', successData.documentId);
      router.push('/analysis');
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">Upload Company SOP Document</h1>
        <p className="text-sm text-slate-400 mt-1">
          Configure your SME profile and upload internal procedures to index into ChromaDB vector store.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Form Container */}
        <div className="md:col-span-2 space-y-6">
          <form onSubmit={handleSubmit} className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-xl">
            
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Building className="w-5 h-5 text-indigo-400" />
                1. Company Profile
              </h3>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Company Name</label>
                <input
                  type="text"
                  required
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Industry</label>
                  <input
                    type="text"
                    required
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Country</label>
                  <input
                    type="text"
                    disabled
                    value="Bangladesh"
                    className="w-full bg-slate-950/50 border border-slate-800/80 rounded-xl px-4 py-2.5 text-sm text-slate-400 cursor-not-allowed"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Company Description</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
            </div>

            <hr className="border-slate-800" />

            {/* Document Upload Area */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <FileText className="w-5 h-5 text-indigo-400" />
                  2. Internal SOP Document
                </h3>
                <button
                  type="button"
                  onClick={handleUseSampleSOP}
                  className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-3 py-1 rounded-lg font-medium transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Use Sample NBR VAT SOP</span>
                </button>
              </div>

              <div className="border-2 border-dashed border-slate-800 hover:border-indigo-500/50 rounded-2xl p-6 text-center bg-slate-950/40 transition-colors">
                <input
                  type="file"
                  id="sop-upload"
                  accept=".txt,.pdf"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <label htmlFor="sop-upload" className="cursor-pointer block space-y-3">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto">
                    <UploadCloud className="w-6 h-6" />
                  </div>
                  <div>
                    {selectedFile ? (
                      <span className="text-sm font-semibold text-emerald-400 block">{selectedFile.name}</span>
                    ) : (
                      <span className="text-sm text-slate-300 block">Click to upload or drag & drop SOP file (.pdf or .txt)</span>
                    )}
                    <span className="text-xs text-slate-500 mt-1 block">Maximum size 10MB</span>
                  </div>
                </label>
              </div>
            </div>

            {errorMsg && (
              <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-medium">
                {errorMsg}
              </div>
            )}

            {/* Action Buttons */}
            {!successData ? (
              <button
                type="submit"
                disabled={Boolean(loadingStep)}
                className="w-full py-3.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all"
              >
                {loadingStep ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Processing Ingestion Pipeline...</span>
                  </>
                ) : (
                  <>
                    <span>Process & Vectorize Document</span>
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
            ) : (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-sm text-emerald-400">
                    <CheckCircle2 className="w-5 h-5" />
                    <span>SOP Indexed into ChromaDB Successfully!</span>
                  </div>
                  <p>Document parsed into structured chunks and embedded with `all-MiniLM-L6-v2`.</p>
                </div>
                <button
                  type="button"
                  onClick={handleProceedToAnalysis}
                  className="w-full py-3.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-2 transition-all"
                >
                  <span>Proceed to 5-Agent Pipeline Analysis</span>
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            )}

          </form>
        </div>

        {/* Progress Pipeline Info Panel */}
        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
            <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">Ingestion Flow State</h4>
            
            <div className="space-y-3 text-xs">
              <div className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">1</div>
                <div>
                  <div className="font-semibold text-white">Company Profile</div>
                  <div className="text-slate-400">Creates SQLite record</div>
                </div>
              </div>

              <div className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">2</div>
                <div>
                  <div className="font-semibold text-white">PyMuPDF Text Parsing</div>
                  <div className="text-slate-400">Extracts headings & clauses</div>
                </div>
              </div>

              <div className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">3</div>
                <div>
                  <div className="font-semibold text-white">ChromaDB Vector Store</div>
                  <div className="text-slate-400">Indexes dense embeddings</div>
                </div>
              </div>
            </div>

            {loadingStep && (
              <div className="p-3 rounded-xl bg-indigo-950/50 border border-indigo-500/30 text-indigo-300 text-xs flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400 shrink-0" />
                <span>{loadingStep}</span>
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
