import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import type { ReactNode } from 'react';
import { Navbar } from '@/components/Navbar';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';
import { BackendStatus } from '@/components/BackendStatus';
import { AuthProvider } from '@/context/AuthContext';
import { UpgradeModal } from '@/components/UpgradeModal';
import { MeResponse } from '@/lib/types';
import { getServerApiBase } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

function sanitizeNextUrl(rawNext: string | null): string {
  if (!rawNext) return '/';
  if (rawNext.startsWith('//') || rawNext.includes('\\') || rawNext.includes(':')) {
    return '/';
  }
  if (rawNext.startsWith('/')) {
    return rawNext;
  }
  return '/';
}

export default async function AppLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;
  const headersList = await headers();
  const currentPath = sanitizeNextUrl(headersList.get('x-current-path') || '/');

  if (!session) {
    redirect(`/login?next=${encodeURIComponent(currentPath)}`);
  }

  let meData: MeResponse | null = null;
  const apiBase = getServerApiBase();
  const cookieHeader = headersList.get('cookie') || `complianceos_session=${session}`;

  try {
    const res = await fetch(`${apiBase}/me`, {
      headers: {
        Cookie: cookieHeader,
        Authorization: `Bearer ${session}`,
        ...(headersList.get('x-vercel-protection-bypass')
          ? { 'x-vercel-protection-bypass': headersList.get('x-vercel-protection-bypass')! }
          : {}),
      },
      cache: 'no-store',
    });
    if (res.ok) {
      meData = (await res.json()) as MeResponse;
    }
  } catch (err) {
    console.error('Failed to fetch /me in AppLayout:', err);
    meData = null;
  }

  if (!meData) {
    redirect(`/login?reauth=1&next=${encodeURIComponent(currentPath)}`);
  }

  return (
    <AuthProvider initialData={meData}>
      <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased selection:bg-emerald-500 selection:text-white">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <BackendStatus />
          {children}
        </main>
        <UpgradeModal />
        <footer className="border-t border-slate-200/80 bg-white py-6">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
            <div>© 2026 LexGOV AI Technologies Inc. Designed for Bangladeshi SME Compliance.</div>
            <LegalDisclaimer compact />
          </div>
        </footer>
      </div>
    </AuthProvider>
  );
}

