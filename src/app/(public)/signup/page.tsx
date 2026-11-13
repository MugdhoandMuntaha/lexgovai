'use client';

import React, { useState, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowRight, Lock, Mail, Building, User, AlertCircle, CheckCircle2 } from 'lucide-react';
import { signup } from '@/lib/api';
import { clearSession } from '@/lib/session';
import { createClient } from '@/lib/supabase/client';

const COMMON_PASSWORDS = new Set([
  'password',
  'password123',
  'password1234',
  '1234567890',
  '12345678901',
  'qwerty1234',
  'admin12345',
  'administrator',
  'compliance123',
  'complianceos',
  'letmein123',
  'welcome123',
  'pass123456',
  'iloveyou123',
  'bangladesh1',
  'dhaka12345',
  'testing123',
  'changeme123',
  'secret1234',
]);

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

function SignupForm() {
  const searchParams = useSearchParams();
  const rawNext = searchParams.get('next') || searchParams.get('redirect');
  const nextUrl = sanitizeNextUrl(rawNext);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validatePasswordRules = (pwd: string): string | null => {
    if (pwd.length < 10) {
      return 'Password must be at least 10 characters long.';
    }
    if (COMMON_PASSWORDS.has(pwd.toLowerCase())) {
      return 'Password is too common or easily guessed. Please choose a stronger password.';
    }
    if (pwd.trim() !== pwd || /^\s+$/.test(pwd)) {
      return 'Password cannot start or end with whitespace.';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError('Email and password are required.');
      return;
    }

    const pwdError = validatePasswordRules(password);
    if (pwdError) {
      setError(pwdError);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please verify your password confirmation.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const supabase = createClient();
      const { data, error: signUpError } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            full_name: fullName.trim(),
            company_name: companyName.trim(),
          },
        },
      });

      if (!signUpError && data.session) {
        document.cookie = `complianceos_session=${data.session.access_token}; path=/; max-age=604800; SameSite=Lax`;
        clearSession();
        window.location.href = nextUrl;
        return;
      }

      // Fall back to backend signup (for local/mock environments)
      await signup(email, password, fullName.trim() || undefined, companyName.trim() || undefined);
      clearSession();
      window.location.href = nextUrl;
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 409) {
        setError('An account with this email already exists. Please sign in instead.');
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Registration failed. Please check your information and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const isPasswordValidLength = password.length >= 10;
  const isPasswordNotCommon = password.length > 0 && !COMMON_PASSWORDS.has(password.toLowerCase());
  const doPasswordsMatch = password.length > 0 && confirmPassword.length > 0 && password === confirmPassword;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-bold tracking-tight text-slate-900">Create your account</h2>
        <p className="mt-1 text-xs text-slate-500">
          Set up your workspace to automate Bangladeshi regulatory compliance
        </p>
      </div>

      {error && (
        <div className="rounded-xl bg-rose-50 border border-rose-200/80 p-3 text-xs text-rose-700 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-500 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <form className="space-y-3.5" onSubmit={handleSubmit} noValidate>
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1" htmlFor="email">
            Work Email Address *
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="founder@company.com"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 outline-hidden transition-all"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1" htmlFor="password">
            Password *
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 10 characters"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 outline-hidden transition-all"
            />
          </div>
          <div className="mt-1.5 flex items-center gap-3 text-[11px] text-slate-500">
            <span className={`inline-flex items-center gap-1 ${isPasswordValidLength ? 'text-emerald-600 font-medium' : ''}`}>
              <CheckCircle2 className={`h-3 w-3 ${isPasswordValidLength ? 'text-emerald-600' : 'text-slate-300'}`} />
              Min 10 characters
            </span>
            <span className={`inline-flex items-center gap-1 ${isPasswordNotCommon ? 'text-emerald-600 font-medium' : ''}`}>
              <CheckCircle2 className={`h-3 w-3 ${isPasswordNotCommon ? 'text-emerald-600' : 'text-slate-300'}`} />
              Not common
            </span>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1" htmlFor="confirmPassword">
            Confirm Password *
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repeat password"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 outline-hidden transition-all"
            />
          </div>
          {confirmPassword.length > 0 && (
            <p className={`mt-1 text-[11px] ${doPasswordsMatch ? 'text-emerald-600' : 'text-rose-600'}`}>
              {doPasswordsMatch ? '✓ Passwords match' : '✗ Passwords do not match'}
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1" htmlFor="fullName">
            Full Name (optional)
          </label>
          <div className="relative">
            <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              id="fullName"
              name="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Junaid Rahman"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 outline-hidden transition-all"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1" htmlFor="companyName">
            Company / Workspace Name (optional)
          </label>
          <div className="relative">
            <Building className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              id="companyName"
              name="companyName"
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Apex Logistics Ltd"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 outline-hidden transition-all"
            />
          </div>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 py-2.5 px-4 text-sm font-semibold text-white shadow-xs hover:bg-emerald-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:opacity-50 transition-all cursor-pointer"
          >
            <span>{isLoading ? 'Creating account...' : 'Create Account'}</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </form>

      <div className="text-center pt-3 border-t border-slate-100">
        <p className="text-xs text-slate-500">
          Already have an account?{' '}
          <Link
            href={nextUrl !== '/' ? `/login?next=${encodeURIComponent(nextUrl)}` : '/login'}
            className="font-semibold text-emerald-600 hover:text-emerald-500 hover:underline"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="h-96 animate-pulse rounded-lg bg-slate-100" />}>
      <SignupForm />
    </Suspense>
  );
}

