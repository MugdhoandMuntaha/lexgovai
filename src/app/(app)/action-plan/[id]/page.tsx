import React from 'react';
import { cookies } from 'next/headers';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft } from 'lucide-react';
import { ActionPlanClient } from './ActionPlanClient';
import { ActionPlanResponse, FindingReviewItem, FindingReviewsResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

interface ActionPlanPageProps {
  params: Promise<{ id: string }>;
}

export default async function ActionPlanPage({ params }: ActionPlanPageProps) {
  const { id: planId } = await params;
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;

  let plan: ActionPlanResponse | null = null;
  let initialReviews: FindingReviewItem[] = [];
  let initialAdjustedScore = 0;

  if (session && planId) {
    const authHeaders = { Cookie: `complianceos_session=${session}` };
    try {
      const [planRes, reviewsRes] = await Promise.all([
        fetch(`${API_BASE}/action-plans/${encodeURIComponent(planId)}`, { headers: authHeaders, cache: 'no-store' }),
        fetch(`${API_BASE}/finding-reviews?plan_id=${encodeURIComponent(planId)}`, { headers: authHeaders, cache: 'no-store' }),
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
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-slate-900">Action Plan Not Found</h2>
        <p className="text-xs text-slate-500">The requested action plan could not be retrieved.</p>
        <Link
          href="/analysis"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Analysis</span>
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
