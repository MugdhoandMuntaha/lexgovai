'use client';

import React, { useState, useTransition } from 'react';
import {
  Sliders,
  Shield,
  Clock,
  Send,
  Users,
  AlertTriangle,
  CheckCircle2,
  Save,
  BarChart3,
  Calendar,
  Lock,
  Phone,
  Mail,
  MessageSquare,
  HelpCircle,
} from 'lucide-react';
import {
  setComplianceOwner,
  deleteComplianceOwner,
  updateWorkspaceAlertSettings,
  testSendAlert,
} from '@/lib/api';
import { TeamMemberItem } from '@/lib/types';

interface AlertRoutingClientProps {
  initialOwners: any[];
  initialSettings: any;
  teamMembers: TeamMemberItem[];
  initialStats: Record<string, any>;
  userRole: string;
}

const DOMAIN_TAGS: Array<{ tag: string; label: string; regulator: string; hint: string }> = [
  { tag: 'tax_vat', label: 'VAT & Supplementary Duty', regulator: 'NBR', hint: 'VAT and Supplementary Duty Act 2012' },
  { tag: 'income_tax', label: 'Income Tax', regulator: 'NBR', hint: 'Income Tax Act 2023 & statutory orders' },
  { tag: 'customs', label: 'Customs & Tariffs', regulator: 'Customs / NBR', hint: 'Customs Act 2023 and HS code circulars' },
  { tag: 'labor', label: 'Labour & Workplace Safety', regulator: 'DIFE / MoLE', hint: 'Bangladesh Labour Act 2006 & Rules 2015' },
  { tag: 'company_law', label: 'Corporate & RJSC Filings', regulator: 'RJSC / MoC', hint: 'Companies Act 1994 annual compliance' },
  { tag: 'banking', label: 'Banking & Foreign Exchange', regulator: 'Bangladesh Bank', hint: 'Bank Company Act & FE Circulars' },
  { tag: 'securities', label: 'Securities & Capital Markets', regulator: 'BSEC', hint: 'Securities & Exchange Commission rules' },
  { tag: 'environment', label: 'Environmental Clearance', regulator: 'DoE', hint: 'Environment Conservation Act 1995 & ECC' },
  { tag: 'trade', label: 'Import, Export & Trade', regulator: 'CCI&E / MoC', hint: 'Import and Export Control Act 1950' },
  { tag: 'data_privacy', label: 'Cyber Security & Data Privacy', regulator: 'BTRC / CSA', hint: 'Cyber Security Act & digital data safety' },
  { tag: 'general', label: 'General Corporate Governance', regulator: 'Government of Bangladesh', hint: 'Standard enterprise compliance alerts' },
];

export function AlertRoutingClient({
  initialOwners,
  initialSettings,
  teamMembers,
  initialStats,
  userRole,
}: AlertRoutingClientProps) {
  const isAdmin = userRole === 'owner' || userRole === 'admin';
  const [isPending, startTransition] = useTransition();

  // Compliance Owners mapping state: { [tag]: { primary_user_id, backup_user_id } }
  const [ownersMap, setOwnersMap] = useState<Record<string, { primary: string; backup: string }>>(() => {
    const map: Record<string, { primary: string; backup: string }> = {};
    initialOwners.forEach((o) => {
      map[o.domain_tag] = {
        primary: o.primary_user_id || '',
        backup: o.backup_user_id || '',
      };
    });
    return map;
  });

  const [ownerSaveMsg, setOwnerSaveMsg] = useState<string | null>(null);

  // Settings State
  const [quietStart, setQuietStart] = useState(initialSettings.quiet_hours_start || '22:00');
  const [quietEnd, setQuietEnd] = useState(initialSettings.quiet_hours_end || '08:00');
  const [weekendDays, setWeekendDays] = useState<number[]>(initialSettings.weekend_days || [4, 5]); // Fri & Sat
  const [critEscHours, setCritEscHours] = useState(initialSettings.escalation_critical_hours || 4);
  const [highEscHours, setHighEscHours] = useState(initialSettings.escalation_high_hours || 24);
  const [smsCap, setSmsCap] = useState(initialSettings.monthly_sms_cap || 100);
  const [whatsAppCap, setWhatsAppCap] = useState(initialSettings.monthly_whatsapp_cap || 100);
  const [settingsSaveMsg, setSettingsSaveMsg] = useState<string | null>(null);

  // Test Send State
  const [testChannel, setTestChannel] = useState('email');
  const [testRecipient, setTestRecipient] = useState('');
  const [testSubject, setTestSubject] = useState('LexGOV AI Test Alert');
  const [testBody, setTestBody] = useState('This is a test notification from the LexGOV AI Alert Center.');
  const [testSendResult, setTestSendResult] = useState<string | null>(null);
  const [isSendingTest, setIsSendingTest] = useState(false);

  // Save Compliance Owner for a specific domain
  const handleSaveOwner = (tag: string) => {
    if (!isAdmin) return;
    const entry = ownersMap[tag];
    if (!entry?.primary) {
      alert('Please select a Primary Compliance Owner.');
      return;
    }

    startTransition(async () => {
      try {
        setOwnerSaveMsg(`Saving ${tag}...`);
        await setComplianceOwner({
          domain_tag: tag,
          primary_user_id: entry.primary,
          backup_user_id: entry.backup || null,
        });
        setOwnerSaveMsg(`Saved owner for ${tag}!`);
        setTimeout(() => setOwnerSaveMsg(null), 2500);
      } catch (err: any) {
        setOwnerSaveMsg(`Error: ${err.message}`);
      }
    });
  };

  // Delete Compliance Owner
  const handleDeleteOwner = (tag: string) => {
    if (!isAdmin) return;
    startTransition(async () => {
      try {
        await deleteComplianceOwner(tag);
        setOwnersMap((prev) => {
          const next = { ...prev };
          delete next[tag];
          return next;
        });
        setOwnerSaveMsg(`Removed mapping for ${tag}`);
        setTimeout(() => setOwnerSaveMsg(null), 2500);
      } catch (err: any) {
        alert(err.message);
      }
    });
  };

  // Toggle Weekend Day
  const handleToggleWeekend = (day: number) => {
    setWeekendDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()
    );
  };

  // Save Workspace Alert Settings
  const handleSaveSettings = () => {
    if (!isAdmin) return;
    startTransition(async () => {
      try {
        setSettingsSaveMsg('Saving settings...');
        await updateWorkspaceAlertSettings({
          quiet_hours_start: quietStart,
          quiet_hours_end: quietEnd,
          weekend_days: weekendDays,
          escalation_critical_hours: Number(critEscHours),
          escalation_high_hours: Number(highEscHours),
          monthly_sms_cap: Number(smsCap),
          monthly_whatsapp_cap: Number(whatsAppCap),
        });
        setSettingsSaveMsg('Settings updated successfully!');
        setTimeout(() => setSettingsSaveMsg(null), 3000);
      } catch (err: any) {
        setSettingsSaveMsg(`Error: ${err.message}`);
      }
    });
  };

  // Execute Test Send
  const handleExecuteTestSend = async () => {
    if (!testRecipient.trim()) {
      setTestSendResult('Please enter a recipient address (email, phone, or user ID)');
      return;
    }
    setIsSendingTest(true);
    setTestSendResult(null);
    try {
      const res = await testSendAlert({
        channel: testChannel,
        recipient_address: testRecipient.trim(),
        subject: testSubject,
        body: testBody,
      });
      setTestSendResult(`Success: ${JSON.stringify(res.result)}`);
    } catch (err: any) {
      setTestSendResult(`Failed: ${err.message}`);
    } finally {
      setIsSendingTest(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Sliders className="w-6 h-6 text-indigo-600" />
          Alert Routing & Compliance Owners
        </h1>
        <p className="text-sm text-slate-600 mt-1">
          Direct regulatory notifications to domain specialists, configure Bangladesh quiet hours and holidays, and define automated escalation windows.
        </p>
      </div>

      {!isAdmin && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-center gap-3 text-amber-800 text-xs">
          <Lock className="w-4 h-4 shrink-0 text-amber-600" />
          <span>
            You are viewing this configuration in read-only mode. Workspace <strong>Owner</strong> or <strong>Admin</strong> privileges are required to modify alert routing.
          </span>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs">
          <div className="text-[10px] text-slate-500 uppercase font-bold">Total Alerts Dispatched</div>
          <div className="text-xl font-extrabold text-slate-900 mt-1">
            {initialStats.total_alerts ?? 0}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs">
          <div className="text-[10px] text-slate-500 uppercase font-bold">Delivered</div>
          <div className="text-xl font-extrabold text-emerald-600 mt-1">
            {initialStats.delivered ?? 0}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs">
          <div className="text-[10px] text-slate-500 uppercase font-bold">Pending / Held (Quiet Hours)</div>
          <div className="text-xl font-extrabold text-amber-600 mt-1">
            {initialStats.held ?? 0}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs">
          <div className="text-[10px] text-slate-500 uppercase font-bold">Acknowledged</div>
          <div className="text-xl font-extrabold text-indigo-600 mt-1">
            {initialStats.acknowledged ?? 0}
          </div>
        </div>
      </div>

      {/* Compliance Owners Assignment Table */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-600" />
              Domain Compliance Owners
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              When regulatory changes or deadlines occur in a specific domain, alerts are sent directly to the assigned Primary user. If unacknowledged, alerts escalate to the Backup user.
            </p>
          </div>
          {ownerSaveMsg && (
            <span className="text-xs font-semibold text-emerald-600">{ownerSaveMsg}</span>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <th className="py-3 px-4">Regulatory Domain</th>
                <th className="py-3 px-4">Primary Compliance Officer</th>
                <th className="py-3 px-4">Backup Escalate-To Officer</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {DOMAIN_TAGS.map(({ tag, label, regulator, hint }) => {
                const entry = ownersMap[tag] || { primary: '', backup: '' };

                return (
                  <tr key={tag} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-800">{label}</div>
                      <div className="text-[11px] text-slate-500 font-mono mt-0.5">{hint}</div>
                      <span className="inline-block mt-1 text-[10px] px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-semibold border border-indigo-100">
                        {regulator}
                      </span>
                    </td>

                    <td className="py-3.5 px-4">
                      <select
                        disabled={!isAdmin}
                        value={entry.primary}
                        onChange={(e) =>
                          setOwnersMap((prev) => ({
                            ...prev,
                            [tag]: { ...prev[tag], primary: e.target.value },
                          }))
                        }
                        className="w-full max-w-xs text-xs py-1.5 px-2.5 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
                      >
                        <option value="">-- Select Primary User --</option>
                        {teamMembers.map((m) => (
                          <option key={m.user_id} value={m.user_id}>
                            {m.email} ({m.effective_role})
                          </option>
                        ))}
                      </select>
                    </td>

                    <td className="py-3.5 px-4">
                      <select
                        disabled={!isAdmin}
                        value={entry.backup}
                        onChange={(e) =>
                          setOwnersMap((prev) => ({
                            ...prev,
                            [tag]: { ...prev[tag], backup: e.target.value },
                          }))
                        }
                        className="w-full max-w-xs text-xs py-1.5 px-2.5 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
                      >
                        <option value="">-- None (Escalate to Owner) --</option>
                        {teamMembers.map((m) => (
                          <option key={m.user_id} value={m.user_id}>
                            {m.email} ({m.effective_role})
                          </option>
                        ))}
                      </select>
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      {isAdmin && (
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => handleSaveOwner(tag)}
                            className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 transition-colors"
                          >
                            Save
                          </button>
                          {entry.primary && (
                            <button
                              type="button"
                              onClick={() => handleDeleteOwner(tag)}
                              className="px-2 py-1 text-xs text-slate-400 hover:text-rose-600 transition-colors"
                            >
                              Reset
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quiet Hours, Escalations & Rate Caps */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quiet Hours & Escalation Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">Quiet Hours & Escalation Policy</h2>
                <p className="text-xs text-slate-500">Bangladesh Standard Time (BST, UTC+6) schedule.</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            {/* Quiet Hours Window */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-bold text-slate-700">Quiet Hours Start</label>
                <input
                  type="time"
                  disabled={!isAdmin}
                  value={quietStart}
                  onChange={(e) => setQuietStart(e.target.value)}
                  className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-[11px] text-slate-400 mt-0.5">Default: 22:00 BST</p>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-700">Quiet Hours End</label>
                <input
                  type="time"
                  disabled={!isAdmin}
                  value={quietEnd}
                  onChange={(e) => setQuietEnd(e.target.value)}
                  className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-[11px] text-slate-400 mt-0.5">Default: 08:00 BST</p>
              </div>
            </div>

            {/* Weekend Selector */}
            <div>
              <label className="text-xs font-bold text-slate-700">Bangladesh Weekend Days (Held Alerts)</label>
              <div className="flex gap-2 mt-1.5">
                {[
                  { day: 4, name: 'Friday' },
                  { day: 5, name: 'Saturday' },
                  { day: 6, name: 'Sunday' },
                ].map(({ day, name }) => {
                  const isSelected = weekendDays.includes(day);
                  return (
                    <button
                      key={day}
                      type="button"
                      disabled={!isAdmin}
                      onClick={() => handleToggleWeekend(day)}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-xl border transition-all ${
                        isSelected
                          ? 'bg-indigo-600 text-white border-indigo-600'
                          : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      {name}
                    </button>
                  );
                })}
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Held alerts are delivered automatically when the workweek begins at 08:00 BST.
              </p>
            </div>

            {/* Escalation Windows */}
            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
              <div>
                <label className="text-xs font-bold text-slate-700">Critical Alert Escalation</label>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="number"
                    min={1}
                    max={72}
                    disabled={!isAdmin}
                    value={critEscHours}
                    onChange={(e) => setCritEscHours(Number(e.target.value))}
                    className="w-20 px-3 py-1.5 text-xs rounded-xl border border-slate-300 font-mono text-center focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <span className="text-xs text-slate-600 font-medium">hours</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">Default: 4 hours</p>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700">High Alert Escalation</label>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="number"
                    min={1}
                    max={168}
                    disabled={!isAdmin}
                    value={highEscHours}
                    onChange={(e) => setHighEscHours(Number(e.target.value))}
                    className="w-20 px-3 py-1.5 text-xs rounded-xl border border-slate-300 font-mono text-center focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <span className="text-xs text-slate-600 font-medium">hours</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">Default: 24 hours</p>
              </div>
            </div>

            {/* Monthly Caps */}
            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
              <div>
                <label className="text-xs font-bold text-slate-700">Monthly SMS Cap</label>
                <input
                  type="number"
                  min={0}
                  disabled={!isAdmin}
                  value={smsCap}
                  onChange={(e) => setSmsCap(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-700">Monthly WhatsApp Cap</label>
                <input
                  type="number"
                  min={0}
                  disabled={!isAdmin}
                  value={whatsAppCap}
                  onChange={(e) => setWhatsAppCap(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {isAdmin && (
              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                {settingsSaveMsg && (
                  <span className="text-xs font-semibold text-emerald-600">{settingsSaveMsg}</span>
                )}
                <button
                  type="button"
                  onClick={handleSaveSettings}
                  disabled={isPending}
                  className="ml-auto px-4 py-2 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-all flex items-center gap-2"
                >
                  <Save className="w-3.5 h-3.5" />
                  Save Alert Settings
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Channel Diagnostics & Test Send Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
                <Send className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">Channel Diagnostics & Test Send</h2>
                <p className="text-xs text-slate-500">Validate outbound SMTP, SMS gateways, and WhatsApp tokens.</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-bold text-slate-700">Channel</label>
                <select
                  value={testChannel}
                  onChange={(e) => setTestChannel(e.target.value)}
                  className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="in_app">In-App Notification</option>
                  <option value="email">Email (SMTP / SES)</option>
                  <option value="sms">SMS Gateway (SSL Wireless / Generic)</option>
                  <option value="whatsapp">WhatsApp Business (Meta Cloud)</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-700">Recipient Target</label>
                <input
                  type="text"
                  value={testRecipient}
                  onChange={(e) => setTestRecipient(e.target.value)}
                  placeholder={
                    testChannel === 'email'
                      ? 'user@example.com'
                      : testChannel === 'sms' || testChannel === 'whatsapp'
                      ? '+88017XXXXXXXX'
                      : 'User ID'
                  }
                  className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-bold text-slate-700">Subject</label>
              <input
                type="text"
                value={testSubject}
                onChange={(e) => setTestSubject(e.target.value)}
                className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-slate-700">Message Body</label>
              <textarea
                rows={3}
                value={testBody}
                onChange={(e) => setTestBody(e.target.value)}
                className="w-full mt-1 p-2.5 text-xs rounded-xl border border-slate-300 font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <button
              type="button"
              onClick={handleExecuteTestSend}
              disabled={isSendingTest}
              className="w-full py-2 text-xs font-bold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              {isSendingTest ? 'Dispatching...' : 'Dispatch Test Alert'}
            </button>

            {testSendResult && (
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono break-all text-slate-800">
                {testSendResult}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
