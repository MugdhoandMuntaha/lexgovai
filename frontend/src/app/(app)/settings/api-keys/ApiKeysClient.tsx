'use client';

import React, { useState, useTransition } from 'react';
import Link from 'next/link';
import {
  KeyRound,
  Plus,
  Shield,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  Clock,
  Sparkles,
  Terminal,
} from 'lucide-react';
import { ApiKeyItem } from '@/lib/types';
import { createSettingsApiKey, revokeSettingsApiKey } from '@/lib/api';

interface ApiKeysClientProps {
  initialKeys: ApiKeyItem[];
  canManageApiKeys: boolean;
  userPlanId: string;
  currentUserRole: string;
}

const AVAILABLE_SCOPES = [
  { key: 'reports:read', label: 'reports:read', desc: 'Read corporate compliance audit reports & summaries' },
  { key: 'findings:read', label: 'findings:read', desc: 'Access identified statutory gaps and legal citations' },
  { key: 'alerts:read', label: 'alerts:read', desc: 'Retrieve subscribed regulatory changes and SRO diffs' },
  { key: 'checklist:read', label: 'checklist:read', desc: 'Read compliance obligations and calendar checklist' },
];

export function ApiKeysClient({
  initialKeys,
  canManageApiKeys,
  userPlanId,
  currentUserRole,
}: ApiKeysClientProps) {
  const [keys, setKeys] = useState<ApiKeyItem[]>(initialKeys);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [keyName, setKeyName] = useState('');
  const [selectedScopes, setSelectedScopes] = useState<string[]>(['reports:read', 'findings:read']);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [isPending, startTransition] = useTransition();

  const isAdmin = currentUserRole === 'admin' || currentUserRole === 'owner';
  const activeKeys = keys.filter((k) => !k.revoked_at);
  const maxReached = activeKeys.length >= 3;

  const handleCreateKey = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyName.trim()) return;
    setErrorMsg(null);

    startTransition(async () => {
      try {
        const res = await createSettingsApiKey(keyName.trim(), selectedScopes);
        setRevealedSecret(res.secret_key);
        setKeys((prev) => [
          {
            id: res.id,
            workspace_id: res.workspace_id,
            name: res.name,
            prefix: res.prefix,
            scopes: res.scopes,
            last_used_at: null,
            revoked_at: null,
            created_at: res.created_at,
          },
          ...prev,
        ]);
        setKeyName('');
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to create API key.');
      }
    });
  };

  const handleRevokeKey = (keyId: string, name: string) => {
    if (!confirm(`Are you sure you want to revoke API key "${name}"? This action cannot be undone.`)) return;

    startTransition(async () => {
      try {
        await revokeSettingsApiKey(keyId);
        setKeys((prev) =>
          prev.map((k) => (k.id === keyId ? { ...k, revoked_at: new Date().toISOString() } : k))
        );
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Failed to revoke API key.');
      }
    });
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="flex items-center gap-2 text-indigo-600 font-semibold text-xs tracking-wider uppercase mb-1">
            <KeyRound className="w-4 h-4" />
            <span>Developer Platform</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">API Keys & Integrations</h1>
          <p className="text-sm text-slate-600 mt-1">
            Integrate your enterprise accounting, ERP, and internal systems using secure Bearer API tokens.
          </p>
        </div>

        {canManageApiKeys && isAdmin && (
          <div>
            <button
              type="button"
              disabled={maxReached}
              onClick={() => {
                setRevealedSecret(null);
                setErrorMsg(null);
                setShowCreateModal(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
              <span>Generate API Key</span>
            </button>
          </div>
        )}
      </div>

      {/* Plan gate warning if not professional */}
      {!canManageApiKeys && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-50 via-sky-50 to-emerald-50 border border-indigo-100 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-indigo-700 font-bold text-xs uppercase tracking-wider">
              <Sparkles className="w-4 h-4" />
              <span>Professional Enterprise Feature</span>
            </div>
            <h2 className="text-base font-bold text-slate-900">Programmatic API Access & Webhooks</h2>
            <p className="text-xs text-slate-600 max-w-xl">
              API keys allow automated extraction of action plans, real-time alert streams, and checklist synchronization into your existing enterprise workflow.
            </p>
          </div>
          <Link
            href="/pricing"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition-all shrink-0"
          >
            <span>Upgrade to Professional</span>
          </Link>
        </div>
      )}

      {/* Active Keys Overview */}
      {canManageApiKeys && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Keys</span>
              <span className="text-xs font-bold text-indigo-600">{activeKeys.length} / 3</span>
            </div>
            <div className="text-2xl font-extrabold text-slate-900">{activeKeys.length} <span className="text-xs font-medium text-slate-400">of 3 limit</span></div>
            <p className="text-xs text-slate-500">Each workspace can maintain up to 3 concurrent active API keys.</p>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Rate Limit</span>
            <div className="text-2xl font-extrabold text-slate-900">60 <span className="text-xs font-medium text-slate-400">req/min</span></div>
            <p className="text-xs text-slate-500">Sliding 60-second window enforced per API key with HTTP 429 throttling.</p>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Authentication Protocol</span>
            <div className="text-sm font-bold text-slate-800 flex items-center gap-1.5 mt-1">
              <Shield className="w-4 h-4 text-emerald-600" />
              <span>Bearer Token (SHA-256 at rest)</span>
            </div>
            <p className="text-xs text-slate-500">Cookies are rejected on versioned /api/v1 endpoints.</p>
          </div>
        </div>
      )}

      {/* Keys Table */}
      {canManageApiKeys && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <h2 className="text-base font-bold text-slate-900">API Keys ({keys.length})</h2>
            <span className="text-xs text-slate-500 font-medium">Prefix is displayed; secret key is hashed</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50/80 text-xs font-semibold uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3.5">Name & Prefix</th>
                  <th className="px-6 py-3.5">Scopes</th>
                  <th className="px-6 py-3.5">Created</th>
                  <th className="px-6 py-3.5">Last Used</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {keys.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-xs">
                      No API keys created yet. Click &quot;Generate API Key&quot; to begin.
                    </td>
                  </tr>
                ) : (
                  keys.map((k) => (
                    <tr key={k.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900">{k.name}</div>
                        <div className="text-xs font-mono text-slate-500 mt-0.5">{k.prefix}...</div>
                      </td>

                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {k.scopes.map((scope) => (
                            <span
                              key={scope}
                              className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200"
                            >
                              {scope}
                            </span>
                          ))}
                        </div>
                      </td>

                      <td className="px-6 py-4 text-xs text-slate-500 font-mono">
                        {k.created_at ? new Date(k.created_at).toLocaleDateString() : 'N/A'}
                      </td>

                      <td className="px-6 py-4 text-xs text-slate-500 font-mono">
                        {k.last_used_at ? (
                          <span className="flex items-center gap-1 text-slate-700">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            <span>{new Date(k.last_used_at).toLocaleDateString()}</span>
                          </span>
                        ) : (
                          <span className="text-slate-400">Never</span>
                        )}
                      </td>

                      <td className="px-6 py-4 text-right">
                        {k.revoked_at ? (
                          <span className="text-xs font-semibold text-slate-400">Revoked</span>
                        ) : (
                          isAdmin && (
                            <button
                              type="button"
                              onClick={() => handleRevokeKey(k.id, k.name)}
                              disabled={isPending}
                              className="text-xs font-semibold text-rose-600 hover:text-rose-700 hover:underline"
                            >
                              Revoke Key
                            </button>
                          )
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Code Example Preview */}
      <div className="p-6 rounded-2xl bg-slate-900 text-white shadow-xs space-y-3">
        <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs font-semibold">
          <Terminal className="w-4 h-4" />
          <span>Quickstart: Accessing /api/v1</span>
        </div>
        <p className="text-xs text-slate-300">
          External requests authenticate via standard HTTP Authorization Bearer headers. Example curl invocation:
        </p>
        <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-emerald-300 overflow-x-auto">
{`curl -X GET https://api.complianceos.com.bd/api/v1/reports \\
  -H "Authorization: Bearer cos_live_your_api_key_here" \\
  -H "Accept: application/json"`}
        </pre>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl border border-slate-200 shadow-xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">Generate New API Key</h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {!revealedSecret ? (
              <form onSubmit={handleCreateKey} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Key Description / Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. SAP ERP Connector, Bi-weekly Audit Sync"
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-2">
                    Access Scopes
                  </label>
                  <div className="space-y-2">
                    {AVAILABLE_SCOPES.map((scope) => (
                      <label
                        key={scope.key}
                        className="flex items-start gap-2.5 p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors"
                      >
                        <input
                          type="checkbox"
                          checked={selectedScopes.includes(scope.key)}
                          onChange={() => toggleScope(scope.key)}
                          className="mt-0.5 rounded text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <div className="text-xs font-semibold text-slate-900 font-mono">{scope.label}</div>
                          <div className="text-[11px] text-slate-500">{scope.desc}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isPending || !keyName.trim() || selectedScopes.length === 0}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
                  >
                    {isPending ? 'Generating...' : 'Create Key'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                  <div>
                    <strong>Save this secret key immediately!</strong> For security, it will never be displayed again.
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={revealedSecret}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 text-xs font-mono text-slate-800 select-all"
                  />
                  <button
                    type="button"
                    onClick={() => copyToClipboard(revealedSecret)}
                    className="px-3 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold flex items-center gap-1.5 shrink-0 hover:bg-slate-800"
                  >
                    {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
