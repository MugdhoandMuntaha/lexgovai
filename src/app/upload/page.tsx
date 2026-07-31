'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { UploadCloud, FileText, CheckCircle2, ArrowRight, Building, Globe, Shield, RefreshCw } from 'lucide-react';
import { createCompanyProfile, uploadDocument } from '@/lib/api';

export default function UploadPage() {
  const router = useRouter();

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

  const handleUsePresetSample = async () => {
    setLoading(true);
    setError(null);
    try {
      const sampleText = `Standard Operating Procedure: Financial Operations & Compliance (SOP-FIN-2024-v2)
Company: Apex Logistics Bangladesh Ltd.

Section 1: Overview and Purpose
This document governs routine tax, VAT, and accounting procedures.

Section 6.1: VAT Submission Timelines & Responsibilities
The finance and accounts department submits monthly VAT returns to the NBR within 30 calendar days following the tax month end. Any available finance team member is authorized to process filings via the NBR online portal.`;

      const profile = await createCompanyProfile({
        company_name: companyName,
        industry: industry,
        country: country,
        description: 'Dhaka-based freight forwarding and trade logistics SME.',
      });

      const blob = new Blob([sampleText], { type: 'text/plain' });
      const file = new File([blob], 'Apex_Logistics_SOP.txt', { type: 'text/plain' });
      const docRes = await uploadDocument(profile.id, file);

      sessionStorage.setItem('company_profile_id', profile.id);
      sessionStorage.setItem('document_id', docRes.document_id);

      setSuccessMsg('Sample SOP document successfully indexed into ChromaDB vector store!');
      setTimeout(() => {
        router.push('/analysis');
      }, 1200);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to ingest sample document.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a PDF or Text file to upload.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const profile = await createCompanyProfile({
        company_name: companyName,
        industry: industry,
        country: country,
      });

      const docRes = await uploadDocument(profile.id, selectedFile);

      sessionStorage.setItem('company_profile_id', profile.id);
      sessionStorage.setItem('document_id', docRes.document_id);

      setSuccessMsg(`File "${selectedFile.name}" successfully parsed and indexed!`);
      setTimeout(() => {
        router.push('/analysis');
      }, 1200);

    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Upload and indexing failed.');
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
          <span>Ingestion Wizard — ChromaDB Indexing</span>
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">SOP Document Ingestion</h1>
        <p className="text-sm text-slate-500">
          Ingest your company Standard Operating Procedures (PDF or TXT) into the vector store for multi-agent compliance benchmarking.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold">
          {error}
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        
        {/* Step 1: Corporate Profile Metadata */}
        <div className="bg-white border border-slate-200/90 rounded-3xl p-6 space-y-4 shadow-2xs">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">1. Organization Metadata</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Company Name</label>
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

            <div>
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
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">2. Select SOP Document (PDF / TXT)</h3>
            
            <button
              type="button"
              onClick={handleUsePresetSample}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-semibold transition-all"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Load Preset Sample SOP (Bangladeshi SME)</span>
            </button>
          </div>

          <div className="border-2 border-dashed border-slate-200 hover:border-emerald-500 rounded-3xl p-8 text-center bg-slate-50/50 transition-colors relative">
            <input
              type="file"
              accept=".pdf,.txt"
              onChange={handleFileChange}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
            <div className="space-y-3 pointer-events-none">
              <UploadCloud className="w-10 h-10 text-slate-400 mx-auto" />
              {selectedFile ? (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-50 text-emerald-800 text-xs font-semibold border border-emerald-200">
                  <FileText className="w-4 h-4" />
                  <span>{selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-bold text-slate-900">Click or drag & drop SOP file here</p>
                  <p className="text-xs text-slate-500 mt-1">Supports PDF or Plain Text files up to 10MB</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Button */}
        <button
          type="submit"
          disabled={loading || !selectedFile}
          className="w-full py-4 px-6 rounded-2xl bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-sm shadow-sm flex items-center justify-center gap-2 transition-all"
        >
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Parsing and Indexing Document...</span>
            </>
          ) : (
            <>
              <span>Upload SOP & Proceed to Agent Analysis</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>

      </form>

    </div>
  );
}
