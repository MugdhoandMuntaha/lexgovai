import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { createServerClient } from '@supabase/ssr';

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

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  });

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co';
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-anon-key';

  let accessToken: string | null = null;
  let user = null;

  try {
    const supabase = createServerClient(supabaseUrl, supabaseKey, {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    });

    const { data } = await supabase.auth.getUser();
    user = data?.user || null;
    if (user) {
      const { data: sessionData } = await supabase.auth.getSession();
      accessToken = sessionData.session?.access_token || null;
      if (accessToken) {
        response.cookies.set('complianceos_session', accessToken, {
          path: '/',
          httpOnly: true,
          sameSite: 'lax',
          secure: process.env.NODE_ENV === 'production',
        });
      }
    }
  } catch {
    user = null;
  }

  const fallbackSession = request.cookies.get('complianceos_session')?.value;
  const isAuthenticated = Boolean(user || fallbackSession);

  const { pathname, search } = request.nextUrl;
  const isPublicAuthRoute = pathname === '/login' || pathname === '/signup';

  if (!isAuthenticated) {
    if (!isPublicAuthRoute) {
      const fullPath = pathname + search;
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('next', sanitizeNextUrl(fullPath));
      const res = NextResponse.redirect(loginUrl);
      res.headers.set('Cache-Control', 'no-store, max-age=0, must-revalidate');
      return res;
    }
    return response;
  }

  if (isPublicAuthRoute) {
    const nextParam = request.nextUrl.searchParams.get('next');
    const destination = sanitizeNextUrl(nextParam);
    return NextResponse.redirect(new URL(destination, request.url));
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-current-path', sanitizeNextUrl(pathname + search));
  if (accessToken) {
    requestHeaders.set('Authorization', `Bearer ${accessToken}`);
  }

  response.headers.set('Cache-Control', 'no-store, max-age=0, must-revalidate');
  return response;
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
