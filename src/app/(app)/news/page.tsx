import React from 'react';
import { Newspaper, ExternalLink, Filter, Calendar, Tag, Globe, Sparkles } from 'lucide-react';
import { getNews } from '@/lib/api';
import { NewsItem } from '@/lib/types';

interface PageProps {
  searchParams: Promise<{ sector?: string; tag?: string; jurisdiction?: string }>;
}

export default async function NewsPage({ searchParams }: PageProps) {
  const resolvedParams = await searchParams;
  const sector = resolvedParams.sector;
  const tag = resolvedParams.tag;
  const jurisdiction = resolvedParams.jurisdiction;

  let newsItems: NewsItem[] = [];
  let errorMsg: string | null = null;

  try {
    const res = await getNews({ sector, tag, jurisdiction });
    newsItems = res.items || [];
  } catch (err: unknown) {
    errorMsg = err instanceof Error ? err.message : 'Failed to load regulatory news.';
  }

  const sectors = [
    { label: 'All Sectors', value: '' },
    { label: 'Logistics & Freight', value: 'Logistics & Freight' },
    { label: 'E-commerce', value: 'E-commerce' },
    { label: 'Manufacturing & Trade', value: 'Manufacturing & Trade' },
    { label: 'Financial Services', value: 'Financial Services' },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold mb-2 border border-emerald-200">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Official Regulatory Intelligence</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Regulatory News & Gazette Feed</h1>
          <p className="text-sm text-slate-600 mt-1 max-w-2xl">
            Real-time statutory notices, NBR SRO gazettes, and cross-border trade directives affecting Bangladeshi SMEs and international enterprises.
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mr-2">
          <Filter className="w-3.5 h-3.5" />
          <span>Filter by Sector:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {sectors.map((s) => {
            const isSelected = (!sector && s.value === '') || sector === s.value;
            const queryParams = new URLSearchParams();
            if (s.value) queryParams.set('sector', s.value);
            if (tag) queryParams.set('tag', tag);
            const href = `/news${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

            return (
              <a
                key={s.label}
                href={href}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                  isSelected
                    ? 'bg-slate-900 text-white font-semibold shadow-xs'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
              >
                {s.label}
              </a>
            );
          })}
        </div>
      </div>

      {/* Error state */}
      {errorMsg && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          {errorMsg}
        </div>
      )}

      {/* Content list */}
      {!errorMsg && newsItems.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-3xl border border-dashed border-slate-300">
          <Newspaper className="w-12 h-12 text-slate-400 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No Regulatory Bulletins Found</h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">
            No published bulletins match your current filters. Clear the sector filter to see all general directives.
          </p>
          <a
            href="/news"
            className="inline-block mt-4 px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800"
          >
            Clear Filters
          </a>
        </div>
      ) : (
        <div className="grid gap-6">
          {newsItems.map((item) => (
            <article
              key={item.id}
              className="bg-white p-6 rounded-2xl border border-slate-200/90 hover:border-slate-300 transition-all shadow-xs hover:shadow-md space-y-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  {item.sector && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-indigo-50 text-indigo-700 text-[11px] font-semibold border border-indigo-200">
                      <Tag className="w-3 h-3" />
                      {item.sector}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[11px] font-medium border border-slate-200">
                    <Globe className="w-3 h-3" />
                    {item.jurisdiction}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500 font-mono">
                  <Calendar className="w-3.5 h-3.5" />
                  <time dateTime={item.published_at}>
                    {new Date(item.published_at).toLocaleDateString('en-GB', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </time>
                </div>
              </div>

              <div>
                <h2 className="text-lg font-bold text-slate-900 tracking-tight leading-snug">
                  {item.title}
                </h2>
                <p className="text-sm text-slate-600 mt-2 leading-relaxed">
                  {item.content}
                </p>
              </div>

              {item.source_url && (
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600 hover:text-emerald-700 transition-colors"
                  >
                    <span>View Official Source Document</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                  <span className="text-[11px] text-slate-400 font-mono">Verified Gazette Publication</span>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
