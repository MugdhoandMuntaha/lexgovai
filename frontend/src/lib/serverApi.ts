import { cookies, headers } from 'next/headers';

/**
 * Returns the base URL for backend API requests executed inside Server Components.
 * Works across local dev, Vercel preview deployments, and Vercel production deployments.
 */
export function getServerApiBase(): string {
  // 1. Service binding injected by Vercel in multi-service deployment
  if (process.env.BACKEND_INTERNAL_URL) {
    const internal = process.env.BACKEND_INTERNAL_URL.replace(/\/$/, '');
    return `${internal}/api`;
  }
  // 2. Explicit internal or public URL environment variable
  if (process.env.INTERNAL_API_URL) {
    return process.env.INTERNAL_API_URL.replace(/\/$/, '');
  }
  if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.startsWith('http')) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
  }
  // 3. VERCEL_URL automatically injected by Vercel for all deployments
  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}/api`;
  }
  // 4. Local dev fallback
  return 'http://127.0.0.1:8000/api';
}

/**
 * Constructs authentication and routing headers for server-side fetches to the backend.
 * Passes the session cookie and Bearer authorization, plus Vercel protection bypass if present.
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  const cookieStore = await cookies();
  const session = cookieStore.get('complianceos_session')?.value;
  const headersList = await headers();

  const authHeaders: Record<string, string> = {};
  if (session) {
    authHeaders['Cookie'] = `complianceos_session=${session}`;
    authHeaders['Authorization'] = `Bearer ${session}`;
  }

  const bypass = headersList.get('x-vercel-protection-bypass');
  if (bypass) {
    authHeaders['x-vercel-protection-bypass'] = bypass;
  }

  return authHeaders;
}
