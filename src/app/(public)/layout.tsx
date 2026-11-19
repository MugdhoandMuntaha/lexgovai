import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import type { ReactNode } from 'react';
import { getServerApiBase } from '@/lib/serverApi';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function PublicLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;
  const headersList = await headers();
  const currentUrl = headersList.get('x-current-path') || '';
  const isReauth = currentUrl.includes('reauth=1');

  if (session && !isReauth) {
    try {
      const apiBase = getServerApiBase();
      const res = await fetch(`${apiBase}/me`, {
        headers: {
          Cookie: `complianceos_session=${session}`,
          Authorization: `Bearer ${session}`,
        },
        cache: 'no-store',
      });
      if (res.ok) {
        redirect('/');
      }
    } catch {
      // If backend check fails or redirects, allow viewing login/signup
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="text-center mb-6">
          <span className="text-2xl font-black tracking-tight text-slate-900 select-none">
            LexGOV <span className="text-emerald-600">AI</span>
          </span>
          <p className="mt-1 text-xs text-slate-500 font-medium">Enterprise Regulatory & SOP Intelligence</p>
        </div>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200/80 rounded-xl sm:px-10">
          {children}
        </div>
      </div>
    </div>
  );
}
