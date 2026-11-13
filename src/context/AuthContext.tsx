'use client';

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { getMe, logout as apiLogout } from '@/lib/api';
import { clearSession } from '@/lib/session';
import { createClient } from '@/lib/supabase/client';
import { CapabilityDetailItem, MeResponse, PlanId, Subscription, User, Workspace } from '@/lib/types';

interface UpgradeModalState {
  isOpen: boolean;
  featureName?: string;
  requiredPlan?: PlanId;
}

interface AuthContextType {
  user: User | null;
  workspace: Workspace | null;
  subscription: Subscription | null;
  capabilities: Record<string, CapabilityDetailItem>;
  limits: Record<string, number>;
  llmConfigured: boolean;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  hasCapability: (key: string, requiredLevel?: string) => boolean;
  openUpgradeModal: (featureName?: string, requiredPlan?: PlanId) => void;
  closeUpgradeModal: () => void;
  upgradeModalState: UpgradeModalState;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({
  initialData,
  children,
}: {
  initialData: MeResponse;
  children: ReactNode;
}) {
  const [data, setData] = useState<MeResponse>(initialData);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [upgradeModalState, setUpgradeModalState] = useState<UpgradeModalState>({
    isOpen: false,
  });

  const refresh = useCallback(async () => {
    try {
      setIsLoading(true);
      const me = await getMe();
      setData(me);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    clearSession();
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
    } catch {
      // ignore
    }
    document.cookie = 'complianceos_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    try {
      await apiLogout();
    } catch {
      // Proceed even if server call fails
    }
    window.location.href = '/login';
  }, []);

  const hasCapability = useCallback(
    (key: string, requiredLevel = 'on'): boolean => {
      if (!data) return false;
      const cap = data.capabilities[key];
      const currentLevel = typeof cap === 'object' && cap !== null ? cap.current_level : (cap as unknown as string);
      if (!currentLevel || currentLevel === 'off') return false;
      if (requiredLevel === 'on') return currentLevel !== 'off';
      return currentLevel === requiredLevel;
    },
    [data],
  );

  const openUpgradeModal = useCallback((featureName?: string, requiredPlan?: PlanId) => {
    setUpgradeModalState({
      isOpen: true,
      featureName,
      requiredPlan: requiredPlan || 'starter',
    });
  }, []);

  const closeUpgradeModal = useCallback(() => {
    setUpgradeModalState({ isOpen: false });
  }, []);

  const value: AuthContextType = {
    user: data?.user || null,
    workspace: data?.workspace || null,
    subscription: data?.subscription || null,
    capabilities: data?.capabilities || {},
    limits: data?.limits || {},
    llmConfigured: Boolean(data?.llm_configured),
    isLoading,
    error,
    refresh,
    logout,
    hasCapability,
    openUpgradeModal,
    closeUpgradeModal,
    upgradeModalState,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
