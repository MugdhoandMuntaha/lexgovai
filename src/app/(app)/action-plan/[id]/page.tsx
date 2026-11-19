import React from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft } from 'lucide-react';
import { ActionPlanClient } from './ActionPlanClient';
import { ActionPlanResponse, FindingReviewItem, FindingReviewsResponse } from '@/lib/types';
import { getServerApiBase, getAuthHeaders } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

interface ActionPlanPageProps {
  params: Promise<{ id: string }>;
}

export default async function ActionPlanPage({ params }: ActionPlanPageProps) {
  const { id: planId } = await params;
  const apiBase = getServerApiBase();
  const authHeaders = await getAuthHeaders();

  let plan: ActionPlanResponse | null = null;
  let initialReviews: FindingReviewItem[] = [];
  let initialAdjustedScore = 0;

  if (planId) {
    try {
      const [planRes, reviewsRes] = await Promise.all([
        fetch(`${apiBase}/action-plans/${encodeURIComponent(planId)}`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${apiBase}/finding-reviews?plan_id=${encodeURIComponent(planId)}`, { headers: authHeaders, cache: 'no-store' }),
      ]);

      if (planRes.ok) {
        plan = (await planRes.json()) as ActionPlanResponse;
        initialAdjustedScore = plan.impact_score;
      }
      if (reviewsRes.ok) {
        const revData = (await reviewsRes.json()) as FindingReviewsResponse;
        initialReviews = revData.reviews || [];
        initialAdjustedScore = revData.adjusted_impact_score;
      }
    } catch (e) {
      console.error('Failed to load action plan on server', e);
    }
  }

  if (!plan) {
    return (
      <div className="max-w-xl mx-auto text-center space-y-4 py-16">
        <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">Action Plan Not Found</h2>
        <p className="text-xs text-slate-500">
          The requested compliance action plan could not be located or has expired.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>
    );
  }

  return (
    <ActionPlanClient
      plan={plan}
      initialReviews={initialReviews}
      initialAdjustedScore={initialAdjustedScore}
    />
  );
}
