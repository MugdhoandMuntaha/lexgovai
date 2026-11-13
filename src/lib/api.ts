import {
  ActionPlanResponse,
  ApiKeyItem,
  ApiError,
  AssistantMessageItem,
  AssistantThreadItem,
  AuthResponse,
  ChecklistItem,
  CheckoutResponse,
  CommentItem,
  CompanyProfile,
  CreatedApiKeyResponse,
  DocumentUploadResponse,
  FindingReviewItem,
  FindingReviewsResponse,
  HealthResponse,
  MeResponse,
  MonitoredSourceItem,
  MonitoredSubscriptionItem,
  NewsItem,
  NotificationItem,
  PipelineEvent,
  PlanCatalogResponse,
  PlanId,
  QueueStats,
  RegulationChangeResponse,
  RegulationDetailResponse,
  RegulationSourceAdmin,
  RegulationSummary,
  RegulationText,
  RegulationVersionAdmin,
  StarterAnswers,
  StarterGuideResponse,
  StarterSOPRequest,
  Subscription,
  SupportTicketAdmin,
  SupportTicketItem,
  TeamInviteItem,
  TeamMembersResponse,
  UsageMeter,
} from './types';
import { clearSession } from './session';

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api');

/** Throws an ApiError carrying the backend's structured metadata (401, 403, 429) when available. */
async function request<T>(path: string, init?: RequestInit, fallbackMessage = 'Request failed'): Promise<T> {
  let res: Response;
  const options: RequestInit = {
    ...init,
    credentials: 'include',
  };
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch {
    throw new Error(`Cannot reach the backend at ${API_BASE}. Is the API server running?`);
  }
  if (!res.ok) {
    if (res.status === 401 && typeof window !== 'undefined') {
      const current = window.location.pathname;
      if (!current.startsWith('/login') && !current.startsWith('/signup')) {
        clearSession();
        window.location.href = `/login?next=${encodeURIComponent(current + window.location.search)}`;
      }
    }
    let errorData: Record<string, unknown> | null = null;
    let message = `${fallbackMessage} (HTTP ${res.status})`;
    try {
      errorData = (await res.json()) as Record<string, unknown>;
      if (typeof errorData?.detail === 'string') {
        message = errorData.detail;
      } else if (typeof errorData?.message === 'string') {
        message = errorData.message;
      } else if (errorData && typeof errorData.detail === 'object' && errorData.detail !== null) {
        errorData = errorData.detail as Record<string, unknown>;
        if (typeof errorData?.message === 'string') message = errorData.message;
      }
    } catch {
      // non-JSON response body
    }
    throw new ApiError(res.status, message, errorData || undefined);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export function getHealth(): Promise<HealthResponse> {
  return request('/health', undefined, 'Health check failed');
}

// ---------------------------------------------------------------------------
// Auth & Workspaces
// ---------------------------------------------------------------------------

export function login(email: string, password: string): Promise<AuthResponse> {
  return request('/auth/login', json({ email, password }), 'Login failed');
}

export function signup(
  email: string,
  password: string,
  fullName?: string,
  companyName?: string,
): Promise<AuthResponse> {
  return request(
    '/auth/signup',
    json({ email, password, full_name: fullName, company_name: companyName }),
    'Signup failed',
  );
}

export function logout(): Promise<{ ok: boolean }> {
  return request('/auth/logout', { method: 'POST' }, 'Logout failed');
}

export function getMe(): Promise<MeResponse> {
  return request('/auth/me', undefined, 'Failed to fetch current user session');
}

// ---------------------------------------------------------------------------
// Plans, Subscriptions & Metering
// ---------------------------------------------------------------------------

export function getPlans(): Promise<PlanCatalogResponse> {
  return request('/plans', undefined, 'Failed to fetch plans catalog');
}

export function getUsage(): Promise<UsageMeter[]> {
  return request('/usage', undefined, 'Failed to fetch usage metrics');
}

export function createCheckout(targetPlanId: PlanId, billingCycle = 'monthly'): Promise<CheckoutResponse> {
  return request(
    '/billing/checkout',
    json({ plan_id: targetPlanId, target_plan_id: targetPlanId, billing_cycle: billingCycle }),
    'Failed to initialize checkout',
  );
}

export function cancelSubscription(): Promise<Subscription> {
  return request('/subscriptions/cancel', { method: 'POST' }, 'Failed to cancel subscription');
}

export function changeSubscription(planId: PlanId): Promise<Subscription> {
  return request('/subscriptions/change', json({ plan_id: planId }), 'Failed to change subscription plan');
}

// ---------------------------------------------------------------------------
// Checklist
// ---------------------------------------------------------------------------

export function getChecklist(): Promise<ChecklistItem[]> {
  return request('/checklist', undefined, 'Failed to load checklist');
}

export function updateChecklistItem(itemId: string, done: boolean): Promise<ChecklistItem> {
  return request(
    `/checklist/${encodeURIComponent(itemId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ done }),
    },
    'Failed to update checklist item',
  );
}

// ---------------------------------------------------------------------------
// Core Pipeline
// ---------------------------------------------------------------------------

export function createCompanyProfile(data: {
  company_name: string;
  industry: string;
  country?: string;
  description?: string;
}): Promise<CompanyProfile> {
  return request('/company-profile', json(data), 'Failed to create company profile');
}

export function uploadDocument(companyProfileId: string, file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('company_profile_id', companyProfileId);
  formData.append('file', file);
  return request('/documents/upload', { method: 'POST', body: formData }, 'Failed to upload document');
}

export function uploadSampleDocument(companyProfileId: string): Promise<DocumentUploadResponse> {
  return request('/documents/sample', json({ company_profile_id: companyProfileId }), 'Failed to index sample SOP');
}

export function getRegulationText(): Promise<RegulationText> {
  return request('/regulations/current', undefined, 'Failed to load regulation text');
}

export function getRegulationsList(): Promise<RegulationSummary[]> {
  return request('/regulations', undefined, 'Failed to load regulations catalog');
}

export function getRegulationDetail(regulationId: string): Promise<RegulationDetailResponse> {
  return request(`/regulations/${encodeURIComponent(regulationId)}`, undefined, 'Failed to load regulation details');
}

export function detectSpecificRegulationChange(regulationId: string): Promise<RegulationChangeResponse> {
  return request(
    `/regulations/${encodeURIComponent(regulationId)}/detect-change`,
    { method: 'POST' },
    'Watcher agent failed for regulation'
  );
}

export function getStarterGuide(answers: StarterAnswers): Promise<StarterGuideResponse> {
  return request('/starter-guide', json(answers), 'Failed to generate starter policy guide');
}

export function createStarterSOP(req: StarterSOPRequest): Promise<DocumentUploadResponse> {
  return request('/starter-guide/sop', json(req), 'Failed to generate and index starter SOP');
}

export function detectRegulationChange(): Promise<RegulationChangeResponse> {
  return request('/regulations/detect-change', { method: 'POST' }, 'Watcher agent failed');
}

export function runAnalysis(
  companyProfileId: string,
  documentId: string,
  regulationId?: string
): Promise<ActionPlanResponse> {
  const payload: Record<string, unknown> = {
    company_profile_id: companyProfileId,
    document_id: documentId,
  };
  if (regulationId) {
    payload.regulation_id = regulationId;
  }
  return request(
    '/analyze',
    json(payload),
    'Failed to run multi-agent analysis pipeline',
  );
}

/**
 * Runs the pipeline via Server-Sent Events, calling `onEvent` for each real agent progress event.
 * Resolves with the final action plan; rejects on transport or agent errors.
 */
export async function streamAnalysis(
  companyProfileId: string,
  documentId: string,
  onEvent: (event: PipelineEvent) => void,
  regulationId?: string,
): Promise<ActionPlanResponse> {
  let res: Response;
  const payload: Record<string, unknown> = {
    company_profile_id: companyProfileId,
    document_id: documentId,
  };
  if (regulationId) {
    payload.regulation_id = regulationId;
  }
  try {
    res = await fetch(`${API_BASE}/analyze/stream`, {
      ...json(payload),
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    });
  } catch {
    throw new Error(`Cannot reach the backend at ${API_BASE}. Is the API server running?`);
  }
  if (!res.ok || !res.body) {
    if (res.status === 401 && typeof window !== 'undefined') {
      const current = window.location.pathname;
      if (!current.startsWith('/login') && !current.startsWith('/signup')) {
        clearSession();
        window.location.href = `/login?next=${encodeURIComponent(current + window.location.search)}`;
      }
    }
    let errorData: Record<string, unknown> | null = null;
    let message = 'Failed to start analysis pipeline';
    try {
      errorData = (await res.json()) as Record<string, unknown>;
      if (typeof errorData?.detail === 'string') message = errorData.detail;
    } catch {
      // non-JSON
    }
    throw new ApiError(res.status, message, errorData || undefined);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary: number;
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = rawEvent
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n');
      if (!data) continue;

      const event = JSON.parse(data) as PipelineEvent;
      onEvent(event);
      if (event.type === 'completed') return event.plan;
      if (event.type === 'error') {
        throw new Error(event.agent ? `Agent ${event.agent} failed: ${event.message}` : event.message);
      }
    }
  }
  throw new Error('The analysis stream ended unexpectedly.');
}

export function getActionPlan(planId: string): Promise<ActionPlanResponse> {
  return request(`/action-plans/${encodeURIComponent(planId)}`, undefined, 'Failed to fetch action plan');
}

export function getDownloadReportUrl(planId: string): string {
  return `${API_BASE}/action-plans/${encodeURIComponent(planId)}/report`;
}

// ---------------------------------------------------------------------------
// S1: News & Notifications
// ---------------------------------------------------------------------------
export function getNews(params?: { sector?: string; jurisdiction?: string; tag?: string }): Promise<{ items: NewsItem[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.sector) query.set('sector', params.sector);
  if (params?.jurisdiction) query.set('jurisdiction', params.jurisdiction);
  if (params?.tag) query.set('tag', params.tag);
  const qStr = query.toString();
  return request(`/news${qStr ? `?${qStr}` : ''}`, undefined, 'Failed to fetch regulatory news');
}

export function getNotifications(unreadOnly = false): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  return request(`/notifications?unread_only=${unreadOnly}`, undefined, 'Failed to fetch notifications');
}

export function markNotificationRead(id: string): Promise<{ ok: boolean }> {
  return request(
    `/notifications/${encodeURIComponent(id)}/read`,
    { method: 'PATCH' },
    'Failed to mark notification as read',
  );
}

export function markAllNotificationsRead(): Promise<{ ok: boolean; count: number }> {
  return request('/notifications/mark-all-read', { method: 'POST' }, 'Failed to mark all as read');
}

// ---------------------------------------------------------------------------
// Admin APIs
// ---------------------------------------------------------------------------
export function getAdminQueue(): Promise<QueueStats> {
  return request('/admin/queue', undefined, 'Failed to fetch admin queue');
}

export function getAdminPendingRegulations(): Promise<{ versions: RegulationVersionAdmin[] }> {
  return request('/admin/regulations/pending', undefined, 'Failed to fetch pending regulations');
}

export function publishAdminRegulationVersion(versionId: string): Promise<{ ok: boolean; version: RegulationVersionAdmin }> {
  return request(`/admin/regulations/versions/${encodeURIComponent(versionId)}/publish`, { method: 'POST' }, 'Failed to publish version');
}

export function rejectAdminRegulationVersion(versionId: string): Promise<{ ok: boolean; version: RegulationVersionAdmin }> {
  return request(`/admin/regulations/versions/${encodeURIComponent(versionId)}/reject`, { method: 'POST' }, 'Failed to reject version');
}

export function getAdminSources(): Promise<RegulationSourceAdmin[]> {
  return request('/admin/sources', undefined, 'Failed to fetch sources');
}

export function triggerSourcePoll(sourceId: string): Promise<{ ok: boolean; message: string }> {
  return request(`/admin/sources/${encodeURIComponent(sourceId)}/poll`, { method: 'POST' }, 'Failed to trigger poll');
}

export function createAdminNews(data: { title: string; content: string; sector?: string; jurisdiction?: string; source_url?: string }): Promise<NewsItem> {
  return request('/admin/news', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 'Failed to create news item');
}

export function getAdminTickets(status?: string): Promise<SupportTicketAdmin[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : '';
  return request(`/admin/support/tickets${q}`, undefined, 'Failed to fetch support tickets');
}

export function updateAdminTicket(id: string, status: string): Promise<SupportTicketAdmin> {
  return request(`/admin/support/tickets/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }, 'Failed to update support ticket');
}

// ---------------------------------------------------------------------------
// S2: Monitoring & Subscriptions
// ---------------------------------------------------------------------------
export function getMonitoringSources(): Promise<{ sources: MonitoredSourceItem[] }> {
  return request('/monitoring/sources', undefined, 'Failed to fetch monitoring sources');
}

export function getMonitoringSubscriptions(): Promise<{ subscriptions: MonitoredSubscriptionItem[] }> {
  return request('/monitoring/subscriptions', undefined, 'Failed to fetch monitoring subscriptions');
}

export function subscribeMonitor(regulationId: string): Promise<MonitoredSubscriptionItem> {
  return request(
    '/monitoring/subscriptions',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ regulation_id: regulationId }),
    },
    'Failed to subscribe to source monitoring',
  );
}

export function unsubscribeMonitor(regulationId: string): Promise<{ ok: boolean }> {
  return request(
    `/monitoring/subscriptions/${encodeURIComponent(regulationId)}`,
    { method: 'DELETE' },
    'Failed to unsubscribe from source monitoring',
  );
}

// ---------------------------------------------------------------------------
// S4: AI Compliance Assistant
// ---------------------------------------------------------------------------
export function getAssistantThreads(): Promise<{ threads: AssistantThreadItem[] }> {
  return request('/assistant/threads', undefined, 'Failed to fetch assistant threads');
}

export function getAssistantThreadMessages(threadId: string): Promise<{ messages: AssistantMessageItem[] }> {
  return request(`/assistant/threads/${encodeURIComponent(threadId)}/messages`, undefined, 'Failed to fetch thread messages');
}

export function deleteAssistantThread(threadId: string): Promise<{ ok: boolean }> {
  return request(`/assistant/threads/${encodeURIComponent(threadId)}`, { method: 'DELETE' }, 'Failed to delete thread');
}

// ---------------------------------------------------------------------------
// S5: Team Collaboration & Reviews
// ---------------------------------------------------------------------------
export function getTeamMembers(): Promise<TeamMembersResponse> {
  return request('/team/members', undefined, 'Failed to fetch team members');
}

export function updateTeamMemberRole(userId: string, role: string): Promise<{ success: boolean }> {
  return request(
    `/team/members/${encodeURIComponent(userId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    },
    'Failed to update member role',
  );
}

export function removeTeamMember(userId: string): Promise<{ success: boolean }> {
  return request(
    `/team/members/${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
    'Failed to remove team member',
  );
}

export function getTeamInvites(): Promise<TeamInviteItem[]> {
  return request('/team/invites', undefined, 'Failed to fetch active invites');
}

export function createTeamInvite(
  email: string,
  role: string,
): Promise<{ id: string; email: string; role: string; token: string; expires_at: string }> {
  return request(
    '/team/invites',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, role }),
    },
    'Failed to send team invitation',
  );
}

export function revokeTeamInvite(inviteId: string): Promise<{ success: boolean }> {
  return request(
    `/team/invites/${encodeURIComponent(inviteId)}`,
    { method: 'DELETE' },
    'Failed to revoke invitation',
  );
}

export function acceptTeamInvite(token: string): Promise<{ status: string; workspace_id: string; role: string }> {
  return request(
    '/team/invites/accept',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    },
    'Failed to accept invitation',
  );
}

export function getFindingReviews(planId: string): Promise<FindingReviewsResponse> {
  return request(`/finding-reviews?plan_id=${encodeURIComponent(planId)}`, undefined, 'Failed to fetch finding reviews');
}

export function submitFindingReview(
  planId: string,
  findingId: string,
  status: 'approved' | 'rejected' | 'edited',
  note?: string,
  editedCitation?: string,
): Promise<{ review: FindingReviewItem; adjusted_impact_score: number }> {
  return request(
    '/finding-reviews',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plan_id: planId,
        finding_id: findingId,
        status,
        note,
        edited_citation: editedCitation,
      }),
    },
    'Failed to submit finding review',
  );
}

export function getComments(resourceType: 'finding' | 'checklist_item', resourceId: string): Promise<CommentItem[]> {
  return request(
    `/comments?resource_type=${encodeURIComponent(resourceType)}&resource_id=${encodeURIComponent(resourceId)}`,
    undefined,
    'Failed to fetch comments',
  );
}

export function createComment(
  resourceType: 'finding' | 'checklist_item',
  resourceId: string,
  content: string,
): Promise<CommentItem> {
  return request(
    '/comments',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resource_type: resourceType,
        resource_id: resourceId,
        content,
      }),
    },
    'Failed to post comment',
  );
}

// ---------------------------------------------------------------------------
// S6: API Integrations
// ---------------------------------------------------------------------------
export function getSettingsApiKeys(): Promise<ApiKeyItem[]> {
  return request('/settings/api-keys', undefined, 'Failed to fetch API keys');
}

export function createSettingsApiKey(name: string, scopes: string[]): Promise<CreatedApiKeyResponse> {
  return request(
    '/settings/api-keys',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, scopes }),
    },
    'Failed to generate API key',
  );
}

export function revokeSettingsApiKey(keyId: string): Promise<{ success: boolean }> {
  return request(
    `/settings/api-keys/${encodeURIComponent(keyId)}`,
    { method: 'DELETE' },
    'Failed to revoke API key',
  );
}

// ---------------------------------------------------------------------------
// S7: Customer Support Ticketing
// ---------------------------------------------------------------------------
export function getSupportTickets(): Promise<SupportTicketItem[]> {
  return request('/support/tickets', undefined, 'Failed to fetch support tickets');
}

export function createSupportTicket(
  subject: string,
  message: string,
): Promise<{ ticket: SupportTicketItem; priority: string; sla: string }> {
  return request(
    '/support/tickets',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, message }),
    },
    'Failed to create support ticket',
  );
}

// ---------------------------------------------------------------------------
// Bangladesh Legal Library
// ---------------------------------------------------------------------------

export function getLaws(params?: {
  q?: string;
  law_type?: string;
  domain_tag?: string;
  status?: string;
  year?: number;
  page?: number;
  per_page?: number;
}): Promise<{ laws: import('./types').LawItem[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.q) query.set('q', params.q);
  if (params?.law_type) query.set('law_type', params.law_type);
  if (params?.domain_tag) query.set('domain_tag', params.domain_tag);
  if (params?.status) query.set('status', params.status);
  if (params?.year) query.set('year', params.year.toString());
  if (params?.page) query.set('page', params.page.toString());
  if (params?.per_page) query.set('per_page', params.per_page.toString());
  const qs = query.toString();
  return request(`/laws${qs ? `?${qs}` : ''}`, undefined, 'Failed to fetch laws');
}

export function getLawCoverage(): Promise<import('./types').LawCoverageResponse> {
  return request('/laws/coverage', undefined, 'Failed to fetch legal library coverage');
}

export function searchLaws(q: string, limit = 10): Promise<{ hits: import('./types').LawSearchHit[]; total: number }> {
  const query = new URLSearchParams({ q, limit: limit.toString() });
  return request(`/laws/search?${query.toString()}`, undefined, 'Failed to search laws');
}

export function getRecommendedLaws(): Promise<{
  recommended: Array<{ law: import('./types').LawItem; reason: string }>;
}> {
  return request('/laws/recommended', undefined, 'Failed to fetch recommended laws');
}

export function getLawWatchlist(): Promise<{ watchlist: import('./types').LawItem[] }> {
  return request('/laws/watchlist', undefined, 'Failed to fetch law watchlist');
}

export function getLawDetail(lawId: string): Promise<import('./types').LawDetailResponse> {
  return request(`/laws/${encodeURIComponent(lawId)}`, undefined, 'Failed to fetch law details');
}

export function getLawSections(
  lawId: string,
  versionId?: string,
): Promise<{ sections: import('./types').LawSectionItem[] }> {
  const qs = versionId ? `?version_id=${encodeURIComponent(versionId)}` : '';
  return request(`/laws/${encodeURIComponent(lawId)}/sections${qs}`, undefined, 'Failed to fetch law sections');
}

export function getLawSection(
  lawId: string,
  sectionId: string,
): Promise<import('./types').LawSectionItem> {
  return request(
    `/laws/${encodeURIComponent(lawId)}/sections/${encodeURIComponent(sectionId)}`,
    undefined,
    'Failed to fetch law section',
  );
}

export function getLawVersions(
  lawId: string,
): Promise<{ versions: import('./types').LawVersionItem[] }> {
  return request(`/laws/${encodeURIComponent(lawId)}/versions`, undefined, 'Failed to fetch law versions');
}

export function getLawDiff(
  lawId: string,
  fromVersionId: string,
  toVersionId: string,
): Promise<{
  law_id: string;
  from_version_id: string;
  to_version_id: string;
  diffs: Array<{
    number_label: string;
    heading?: string | null;
    change_type: 'added' | 'removed' | 'modified' | 'unchanged';
    old_text?: string | null;
    new_text?: string | null;
  }>;
}> {
  const qs = new URLSearchParams({
    from_version_id: fromVersionId,
    to_version_id: toVersionId,
  }).toString();
  return request(`/laws/${encodeURIComponent(lawId)}/diff?${qs}`, undefined, 'Failed to compute law diff');
}

export function watchLaw(lawId: string): Promise<{ ok: boolean; is_watched: boolean }> {
  return request(
    `/laws/${encodeURIComponent(lawId)}/watch`,
    { method: 'POST' },
    'Failed to add law to watchlist',
  );
}

export function unwatchLaw(lawId: string): Promise<{ ok: boolean; is_watched: boolean }> {
  return request(
    `/laws/${encodeURIComponent(lawId)}/watch`,
    { method: 'DELETE' },
    'Failed to remove law from watchlist',
  );
}

export function askLaw(
  question: string,
  lawId?: string,
): Promise<{
  answer: string;
  citations: Array<{ section_number: string; snippet: string; verified: boolean }>;
  is_in_scope: boolean;
}> {
  return request(
    '/laws/ask',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, law_id: lawId }),
    },
    'Failed to ask legal assistant',
  );
}

export function analyzeLawAgainstSOP(
  lawId: string,
  companyProfileId: string,
  documentId: string,
): Promise<ActionPlanResponse> {
  return request(
    `/laws/${encodeURIComponent(lawId)}/analyze`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_profile_id: companyProfileId,
        document_id: documentId,
      }),
    },
    'Failed to trigger law analysis',
  );
}

// ---------------------------------------------------------------------------
// Admin Legal Library Endpoints
// ---------------------------------------------------------------------------

export function getAdminLawReviewQueue(): Promise<{
  queue: Array<{
    queue_id: string;
    law_id: string;
    reason: string;
    created_at: string;
    law: import('./types').LawItem;
    version?: import('./types').LawVersionItem | null;
  }>;
}> {
  return request('/admin/laws/review-queue', undefined, 'Failed to fetch review queue');
}

export function approveLaw(lawId: string): Promise<{ ok: boolean; status: string }> {
  return request(
    `/admin/laws/${encodeURIComponent(lawId)}/approve`,
    { method: 'POST' },
    'Failed to approve law',
  );
}

export function rejectLaw(lawId: string, reason: string): Promise<{ ok: boolean; status: string }> {
  return request(
    `/admin/laws/${encodeURIComponent(lawId)}/reject`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    },
    'Failed to reject law',
  );
}

export function updateLawMetadata(
  lawId: string,
  data: Partial<import('./types').LawItem>,
): Promise<{ ok: boolean; law: import('./types').LawItem }> {
  return request(
    `/admin/laws/${encodeURIComponent(lawId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    },
    'Failed to update law metadata',
  );
}

export function getAdminLawSources(): Promise<{ sources: import('./types').LawSourceItem[] }> {
  return request('/admin/laws/sources', undefined, 'Failed to fetch law sources');
}

export function updateAdminLawSource(
  sourceId: string,
  data: Partial<import('./types').LawSourceItem>,
): Promise<{ ok: boolean; source: import('./types').LawSourceItem }> {
  return request(
    `/admin/laws/sources/${encodeURIComponent(sourceId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    },
    'Failed to update law source',
  );
}

export function triggerLawIngestRun(sourceId?: string): Promise<{ ok: boolean; message: string; job_id: string }> {
  return request(
    '/admin/laws/ingest/run',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_id: sourceId }),
    },
    'Failed to trigger ingest run',
  );
}

export async function uploadLawDocument(formData: FormData): Promise<{
  ok: boolean;
  law_id: string;
  publish_state: string;
  ocr_quality?: number | null;
}> {
  const res = await fetch(`${API_BASE}/admin/laws/upload`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed with status ${res.status}`);
  }
  return res.json();
}
