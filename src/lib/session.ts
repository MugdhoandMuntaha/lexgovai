'use client';

import { StarterAnswers } from './types';

/** The company + SOP document currently being analysed, kept in sessionStorage between pages. */
export interface Workspace {
  companyProfileId: string;
  companyName: string;
  documentId: string;
  documentName: string;
  sections: string[];
  regulationId?: string;
  regulationTitle?: string;
}

const KEY = 'complianceos.workspace';
const STARTER_ANSWERS_KEY = 'complianceos.starter_answers';
const STARTER_STEP_KEY = 'complianceos.starter_step';

export function saveWorkspace(workspace: Workspace): void {
  sessionStorage.setItem(KEY, JSON.stringify(workspace));
}

export function loadWorkspace(): Workspace | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Workspace) : null;
  } catch {
    return null;
  }
}

export function saveStarterAnswers(answers: Partial<StarterAnswers>): void {
  try {
    sessionStorage.setItem(STARTER_ANSWERS_KEY, JSON.stringify(answers));
  } catch {
    // Ignore storage quota or access issues
  }
}

export function loadStarterAnswers(): Partial<StarterAnswers> {
  try {
    const raw = sessionStorage.getItem(STARTER_ANSWERS_KEY);
    return raw ? (JSON.parse(raw) as Partial<StarterAnswers>) : {};
  } catch {
    return {};
  }
}

export function saveStarterStep(step: number): void {
  try {
    sessionStorage.setItem(STARTER_STEP_KEY, String(step));
  } catch {
    // Ignore
  }
}

export function loadStarterStep(): number {
  try {
    const raw = sessionStorage.getItem(STARTER_STEP_KEY);
    const parsed = raw ? parseInt(raw, 10) : 0;
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  } catch {
    return 0;
  }
}

export function clearStarterSession(): void {
  try {
    sessionStorage.removeItem(STARTER_ANSWERS_KEY);
    sessionStorage.removeItem(STARTER_STEP_KEY);
  } catch {
    // Ignore
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(KEY);
    sessionStorage.removeItem(STARTER_ANSWERS_KEY);
    sessionStorage.removeItem(STARTER_STEP_KEY);
  } catch {
    // Ignore
  }
}

