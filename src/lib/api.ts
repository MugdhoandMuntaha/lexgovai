import { ActionPlanResponse, CompanyProfile, RegulationChangeResponse } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export async function createCompanyProfile(data: {
  company_name: string;
  industry: string;
  country?: string;
  description?: string;
}): Promise<CompanyProfile> {
  const res = await fetch(`${API_BASE}/company-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create company profile');
  return res.json();
}

export async function uploadDocument(companyProfileId: string, file: File) {
  const formData = new FormData();
  formData.append('company_profile_id', companyProfileId);
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to upload document');
  return res.json();
}

export async function detectRegulationChange(): Promise<RegulationChangeResponse> {
  const res = await fetch(`${API_BASE}/regulations/detect-change`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to detect regulation change');
  return res.json();
}

export async function runAnalysis(companyProfileId: string, documentId: string): Promise<ActionPlanResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company_profile_id: companyProfileId,
      document_id: documentId,
    }),
  });
  if (!res.ok) throw new Error('Failed to run multi-agent analysis pipeline');
  return res.json();
}

export async function getActionPlan(planId: string): Promise<ActionPlanResponse> {
  const res = await fetch(`${API_BASE}/action-plans/${planId}`);
  if (!res.ok) throw new Error('Failed to fetch action plan');
  return res.json();
}

export function getDownloadReportUrl(planId: string): string {
  return `${API_BASE}/action-plans/${planId}/report`;
}
