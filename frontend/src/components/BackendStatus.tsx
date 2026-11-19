'use client';
import React, { useEffect, useState } from 'react';
import { AlertTriangle, ServerCrash } from 'lucide-react';
import { getHealth } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

/** Warns when the backend is unreachable or has no Gemini API key, so failures aren't a mystery. */
export const BackendStatus = () => {
  const { llmConfigured } = useAuth();
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    getHealth()
      .then(() => setOffline(false))
      .catch(() => setOffline(true));
  }, []);

  if (offline) {
    return (
      <div className="mb-6 p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center gap-2">
        <ServerCrash className="w-4 h-4 shrink-0" />
        <span>
          Backend API is not reachable. Start it with{' '}
          <code className="font-mono bg-rose-100 px-1 rounded">uvicorn app.main:create_app --factory --port 8000</code>{' '}
          in the <code className="font-mono bg-rose-100 px-1 rounded">backend</code> folder.
        </span>
      </div>
    );
  }

  if (!llmConfigured) {
    return (
      <div className="mb-6 p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
        <span>
          Backend is running but <code className="font-mono bg-amber-100 px-1 rounded">GEMINI_API_KEY</code> is not set.
          Regulation text is viewable, but ingestion and analysis are disabled until you add the key to{' '}
          <code className="font-mono bg-amber-100 px-1 rounded">backend/.env</code>.
        </span>
      </div>
    );
  }

  return null;
};
