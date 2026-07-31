export interface CitationRef {
  source: string;
  section: string;
  text_snippet: string;
}

export interface FindingDetail {
  id?: string;
  issue: string;
  issue_type: 'gap' | 'conflict' | 'outdated_reference';
  severity: 'low' | 'medium' | 'high';
  explanation: string;
  citation: CitationRef;
  confidence: number;
  flagged_for_review: boolean;
}

export interface ActionPlanResponse {
  id: string;
  company: string;
  regulation: string;
  change_summary: string;
  impact_score: number;
  urgency: string;
  findings: FindingDetail[];
  policy_draft: string[];
  technical_fixes: string[];
  disclaimer: string;
  created_at?: string;
}

export interface CompanyProfile {
  id: string;
  company_name: string;
  industry: string;
  country: string;
  description?: string;
}

export interface RegulationChangeResponse {
  regulation_id: string;
  title: string;
  version_hash: string;
  change_summary: string;
  changed_clauses: string[];
  change_type: string;
}
