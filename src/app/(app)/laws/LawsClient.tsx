'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  BookOpen,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Bell,
  Sparkles,
  Layers,
  ArrowRight,
  ShieldCheck,
  Building2,
} from 'lucide-react';
import { LawItem, LawCoverageResponse } from '@/lib/types';
import { watchLaw, unwatchLaw } from '@/lib/api';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

interface LawsClientProps {
  initialLaws: LawItem[];
  totalCount: number;
  coverage: LawCoverageResponse | null;
  recommended: Array<{ law: LawItem; reason: string }>;
  currentParams: {
    q?: string;
    law_type?: string;
    domain_tag?: string;
    status?: string;
    year?: string;
    page?: string;
  };
}

const LAW_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'act', label: 'Acts' },
  { value: 'ordinance', label: 'Ordinances' },
  { value: 'sro', label: 'SROs' },
  { value: 'rule', label: 'Rules' },
  { value: 'circular', label: 'Circulars' },
  { value: 'order', label: 'Orders' },
  { value: 'gazette_notice', label: 'Gazette Notices' },
];

const DOMAIN_TAGS = [
  { value: '', label: 'All Domains' },
  { value: 'tax_vat', label: 'Tax & VAT' },
  { value: 'banking_finance', label: 'Banking & Finance' },
  { value: 'labor', label: 'Labor & Employment' },
  { value: 'customs', label: 'Customs & Tariffs' },
  { value: 'data_privacy', label: 'Data & Cybersecurity' },
  { value: 'corporate', label: 'Company & Corporate' },
  { value: 'securities', label: 'Securities & Capital' },
  { value: 'foreign_exchange', label: 'Foreign Exchange' },
];

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'in_force', label: 'In Force' },
  { value: 'amended', label: 'Amended' },
  { value: 'repealed', label: 'Repealed' },
];

export function LawsClient({
  initialLaws,
  totalCount,
  coverage,
  recommended,
  currentParams,
}: LawsClientProps) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState(currentParams.q || '');
  const [selectedType, setSelectedType] = useState(currentParams.law_type || '');
  const [selectedTag, setSelectedTag] = useState(currentParams.domain_tag || '');
  const [selectedStatus, setSelectedStatus] = useState(currentParams.status || '');
  const [selectedYear, setSelectedYear] = useState(currentParams.year || '');
  const [watchlistMap, setWatchlistMap] = useState<Record<string, boolean>>({});
  const [isUpdatingWatch, setIsUpdatingWatch] = useState<Record<string, boolean>>({});

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = new URLSearchParams();
    if (searchQuery.trim()) query.set('q', searchQuery.trim());
    if (selectedType) query.set('law_type', selectedType);
    if (selectedTag) query.set('domain_tag', selectedTag);
    if (selectedStatus) query.set('status', selectedStatus);
    if (selectedYear) query.set('year', selectedYear);
    router.push(`/laws?${query.toString()}`);
  };

  const handleFilterChange = (
    key: 'law_type' | 'domain_tag' | 'status' | 'year',
    value: string,
  ) => {
    const query = new URLSearchParams();
    if (searchQuery.trim()) query.set('q', searchQuery.trim());
    const nextType = key === 'law_type' ? value : selectedType;
    const nextTag = key === 'domain_tag' ? value : selectedTag;
    const nextStatus = key === 'status' ? value : selectedStatus;
    const nextYear = key === 'year' ? value : selectedYear;

    if (key === 'law_type') setSelectedType(value);
    if (key === 'domain_tag') setSelectedTag(value);
    if (key === 'status') setSelectedStatus(value);
    if (key === 'year') setSelectedYear(value);

    if (nextType) query.set('law_type', nextType);
    if (nextTag) query.set('domain_tag', nextTag);
    if (nextStatus) query.set('status', nextStatus);
    if (nextYear) query.set('year', nextYear);
    router.push(`/laws?${query.toString()}`);
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setSelectedType('');
    setSelectedTag('');
    setSelectedStatus('');
    setSelectedYear('');
    router.push('/laws');
  };

  const handleToggleWatch = async (lawId: string, currentWatched: boolean) => {
    setIsUpdatingWatch((prev) => ({ ...prev, [lawId]: true }));
    try {
      if (currentWatched) {
        await unwatchLaw(lawId);
        setWatchlistMap((prev) => ({ ...prev, [lawId]: false }));
      } else {
        await watchLaw(lawId);
        setWatchlistMap((prev) => ({ ...prev, [lawId]: true }));
      }
    } catch (err) {
      console.error('Failed to toggle watch status:', err);
    } finally {
      setIsUpdatingWatch((prev) => ({ ...prev, [lawId]: false }));
    }
  };

  return (
    <div className="space-y-8 py-4">
      {/* Top Banner / Hero */}
      <div className="relative overflow-hidden rounded-3xl bg-slate-900 border border-slate-800 p-6 sm:p-8 text-white shadow-md">
        <div className="relative z-10 max-w-4xl space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
            <BookOpen className="w-3.5 h-3.5" />
            <span>Authoritative Bangladesh Legal Library</span>
          </div>

          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white">
            Bangladesh Laws, Regulations & Gazette Enactments
          </h1>

          <p className="text-sm text-slate-300 leading-relaxed max-w-3xl">
            Continuously discovered, structured, classified, and cross-referenced by automated agents from official Bangladesh government portals (BGPress, Ministry of Law, NBR, Bangladesh Bank). Verified against authoritative source texts.
          </p>

          {/* Real Coverage Strip */}
          <div className="pt-2 flex flex-wrap items-center gap-3">
            <div className="px-3.5 py-1.5 rounded-xl bg-slate-800/90 border border-slate-700/80 text-xs text-slate-200 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>
                Coverage:{' '}
                <strong className="text-white font-mono">
                  {coverage?.published_laws_count ?? totalCount}
                </strong>{' '}
                published enactments across{' '}
                <strong className="text-white font-mono">
                  {coverage?.enabled_sources_count ?? 6}
                </strong>{' '}
                monitored sources
              </span>
            </div>

            <div className="px-3.5 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-center gap-1.5 font-medium">
              <span>0 claims of completeness (coverage is ongoing & verifiable)</span>
            </div>

            <Link
              href="/laws/coverage"
              className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors ml-auto"
            >
              <span>View Coverage Dashboard</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>

      {/* Recommended for your company */}
      {recommended.length > 0 && !currentParams.q && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <span>Recommended for Your Company Sector</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recommended.map(({ law, reason }) => (
              <Link
                key={law.id}
                href={`/laws/${law.id}`}
                className="group p-4 rounded-2xl bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm transition-all flex flex-col justify-between gap-3"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] text-slate-500 font-medium">
                    <span className="uppercase tracking-wider font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-md">
                      {law.law_type.replace('_', ' ')}
                    </span>
                    <span>{law.year ? `Year ${law.year}` : law.issuing_body}</span>
                  </div>
                  <h3 className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-2">
                    {law.canonical_title_en}
                  </h3>
                  {law.canonical_title_bn && (
                    <p className="text-[11px] text-slate-500 line-clamp-1 font-sans">
                      {law.canonical_title_bn}
                    </p>
                  )}
                </div>
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                  <span className="text-slate-600 italic line-clamp-1">{reason}</span>
                  <span className="text-indigo-600 font-semibold shrink-0 flex items-center gap-0.5">
                    View <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Main Search & Filters Bar */}
      <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by act title, section keywords, gazette number, or Bengali term (e.g., ভ্যাট আইন, Section 15)..."
              className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
          >
            <Search className="w-3.5 h-3.5" />
            <span>Search Library</span>
          </button>
          {(currentParams.q || currentParams.law_type || currentParams.domain_tag || currentParams.status || currentParams.year) && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="px-3.5 py-2.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs font-semibold transition-colors"
            >
              Reset
            </button>
          )}
        </form>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 text-xs">
          <div className="flex items-center gap-1 text-slate-500 font-medium mr-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </div>

          {/* Law Type Dropdown */}
          <select
            value={selectedType}
            onChange={(e) => handleFilterChange('law_type', e.target.value)}
            className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50/70 text-slate-700 text-xs font-medium focus:outline-none focus:border-slate-400"
          >
            {LAW_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>

          {/* Domain Tag Dropdown */}
          <select
            value={selectedTag}
            onChange={(e) => handleFilterChange('domain_tag', e.target.value)}
            className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50/70 text-slate-700 text-xs font-medium focus:outline-none focus:border-slate-400"
          >
            {DOMAIN_TAGS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>

          {/* Status Dropdown */}
          <select
            value={selectedStatus}
            onChange={(e) => handleFilterChange('status', e.target.value)}
            className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50/70 text-slate-700 text-xs font-medium focus:outline-none focus:border-slate-400"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Laws List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>Enactments & Regulations</span>
            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-mono font-semibold">
              {totalCount}
            </span>
          </h2>
        </div>

        {initialLaws.length === 0 ? (
          <div className="p-12 text-center rounded-2xl bg-white border border-slate-200/90 space-y-3">
            <BookOpen className="w-10 h-10 text-slate-300 mx-auto" />
            <h3 className="text-sm font-bold text-slate-900">No laws found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              No enactments matched your search query or filters. Try adjusting filters or searching for general terms like &quot;tax&quot;, &quot;labor&quot;, or &quot;customs&quot;.
            </p>
            <button
              type="button"
              onClick={handleResetFilters}
              className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
            >
              Clear all filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {initialLaws.map((law) => {
              const isWatched = watchlistMap[law.id] ?? false;
              const isWatchLoading = isUpdatingWatch[law.id] ?? false;

              return (
                <div
                  key={law.id}
                  className="p-5 rounded-2xl bg-white border border-slate-200 hover:border-slate-300 transition-all shadow-2xs space-y-4"
                >
                  {/* Card Header */}
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      {/* Meta Pills */}
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Status Badge */}
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            law.status === 'in_force'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : law.status === 'amended'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : law.status === 'repealed'
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          {law.status.replace('_', ' ')}
                        </span>

                        {/* Law Type */}
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-semibold uppercase tracking-wider font-mono">
                          {law.law_type.replace('_', ' ')}
                        </span>

                        {/* Year & Act Number */}
                        {law.year && (
                          <span className="text-[11px] font-mono text-slate-500">
                            {law.act_number ? `${law.act_number} of ` : ''}
                            {law.year}
                          </span>
                        )}

                        {/* Issuing Body */}
                        <span className="text-[11px] text-slate-500 flex items-center gap-1 font-medium">
                          <Building2 className="w-3 h-3 text-slate-400" />
                          {law.issuing_body}
                        </span>

                        {/* Language */}
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-50 text-slate-600 border border-slate-200 font-mono font-medium">
                          {law.language_available?.toUpperCase() || 'EN'}
                        </span>
                      </div>

                      {/* Canonical Titles */}
                      <Link
                        href={`/laws/${law.id}`}
                        className="block group"
                      >
                        <h3 className="text-base font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                          {law.canonical_title_en}
                        </h3>
                        {law.canonical_title_bn && (
                          <p className="text-xs text-slate-500 font-sans mt-0.5">
                            {law.canonical_title_bn}
                          </p>
                        )}
                      </Link>
                    </div>

                    {/* Quick Watch Button */}
                    <button
                      type="button"
                      onClick={() => handleToggleWatch(law.id, isWatched)}
                      disabled={isWatchLoading}
                      title={isWatched ? 'Unwatch law changes' : 'Watch for regulatory amendments'}
                      className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                        isWatched
                          ? 'bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100'
                          : 'border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                      }`}
                    >
                      <Bell className={`w-3.5 h-3.5 ${isWatched ? 'fill-amber-500 text-amber-500' : 'text-slate-400'}`} />
                      <span>{isWatched ? 'Watching' : 'Watch'}</span>
                    </button>
                  </div>

                  {/* AI Summary with Grounded Verification Badge */}
                  {law.summary_ai && (
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-600">
                          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                          <span>AI Executive Summary</span>
                        </div>

                        {law.summary_verified ? (
                          <div className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 border border-emerald-200 text-[10px] font-bold text-emerald-700">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            <span>Verified against authoritative source</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 border border-amber-200 text-[10px] font-semibold text-amber-700">
                            <AlertTriangle className="w-3 h-3 text-amber-600" />
                            <span>AI generated · Critic verification pending</span>
                          </div>
                        )}
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed">
                        {law.summary_ai}
                      </p>
                    </div>
                  )}

                  {/* Domain Tags & Actions */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {law.domain_tags && law.domain_tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[10px] font-medium"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>

                    <div className="flex items-center gap-2">
                      <Link
                        href={`/laws/${law.id}/diff`}
                        className="px-3 py-1.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                      >
                        <Layers className="w-3.5 h-3.5 text-slate-500" />
                        <span>Compare Versions</span>
                      </Link>

                      <Link
                        href={`/laws/${law.id}`}
                        className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors"
                      >
                        <span>Read Full Text & Sections</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Mandatory Regulatory Disclaimer */}
      <LegalDisclaimer />
    </div>
  );
}
