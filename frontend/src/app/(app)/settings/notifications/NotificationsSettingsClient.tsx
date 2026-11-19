'use client';

import React, { useState, useTransition } from 'react';
import {
  Bell,
  Mail,
  MessageSquare,
  Smartphone,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Calculator,
  Save,
  Send,
  RefreshCw,
  PhoneCall,
  Check,
} from 'lucide-react';
import {
  updateAlertPreferences,
  requestPhoneOtp,
  verifyPhoneOtp,
  optInWhatsApp,
  optOutAlertChannel,
  reOptInAlertChannel,
  previewSmsSegments,
} from '@/lib/api';

interface NotificationsSettingsClientProps {
  initialPreferences: Record<string, Record<string, boolean>>;
  catalog: string[];
  initialChannels: {
    email: { address: string; verified: boolean; opted_out: boolean };
    sms?: { address: string; verified: boolean; opted_out: boolean; locale: string } | null;
    whatsapp?: { address: string; verified: boolean; opted_in: boolean; opted_out: boolean } | null;
  } | null;
}

const EVENT_METADATA: Record<string, { label: string; description: string; category: string }> = {
  regulation_change_detected: {
    label: 'Bangladesh Gazette & Law Updates',
    description: 'Alert when a monitored government gazette or statutory enactment is updated',
    category: 'Regulatory Intelligence',
  },
  law_amendment_watched: {
    label: 'Watched Law Amendments',
    description: 'Instant notification when an act or regulation on your watchlist changes',
    category: 'Regulatory Intelligence',
  },
  deadline_reminder: {
    label: 'Compliance Deadlines (14 / 7 / 1 Day)',
    description: 'Upcoming statutory filing and tax compliance deadline alerts',
    category: 'Deadlines & Tasks',
  },
  high_risk_finding: {
    label: 'High & Critical Risk Findings',
    description: 'Critical gap or severe compliance risk discovered during SOP analysis',
    category: 'Impact Analysis',
  },
  finding_review_needed: {
    label: 'Peer Finding Review Required',
    description: 'When your review is requested on an analysis finding',
    category: 'Team Collaboration',
  },
  export_ready: {
    label: 'Document Studio Export Ready',
    description: 'Notification when your generated PDF/DOCX compliance report is packaged',
    category: 'Document Studio',
  },
  source_blocked_or_failing: {
    label: 'Crawler & Source Outage Alerts',
    description: 'Portal crawler failure, IP block, or CAPTCHA detected (Admins only)',
    category: 'System Health',
  },
  quota_nearing_limit: {
    label: 'Quota & Usage Alerts (80% / 100%)',
    description: 'When monthly analysis tokens, SMS, or storage capacity approach limit',
    category: 'Account & Billing',
  },
  security_event: {
    label: 'Security & Sign-in Alerts',
    description: 'New device sign-in, password reset, or API key generation',
    category: 'Security',
  },
  ack_overdue_escalation: {
    label: 'Unacknowledged Alert Escalations',
    description: 'Escalation notification when a critical alert remains unacknowledged',
    category: 'System Health',
  },
};

export function NotificationsSettingsClient({
  initialPreferences,
  catalog,
  initialChannels,
}: NotificationsSettingsClientProps) {
  // Preference Matrix State
  const [preferences, setPreferences] = useState<Record<string, Record<string, boolean>>>(() => {
    const p: Record<string, Record<string, boolean>> = {};
    const events = catalog.length > 0 ? catalog : Object.keys(EVENT_METADATA);
    events.forEach((ev) => {
      p[ev] = {
        in_app: initialPreferences[ev]?.in_app ?? true,
        email: initialPreferences[ev]?.email ?? true,
        sms: initialPreferences[ev]?.sms ?? (ev === 'high_risk_finding' || ev === 'ack_overdue_escalation'),
        whatsapp: initialPreferences[ev]?.whatsapp ?? false,
      };
    });
    return p;
  });

  const [channels, setChannels] = useState(initialChannels);
  const [isPending, startTransition] = useTransition();
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  // Phone OTP Verification State
  const [phoneNumberInput, setPhoneNumberInput] = useState('');
  const [otpCodeInput, setOtpCodeInput] = useState('');
  const [isOtpSent, setIsOtpSent] = useState(false);
  const [maskedPhone, setMaskedPhone] = useState('');
  const [otpError, setOtpError] = useState<string | null>(null);
  const [otpSuccess, setOtpSuccess] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  // WhatsApp Opt-in state
  const [whatsAppConsent, setWhatsAppConsent] = useState(false);
  const [whatsAppStatus, setWhatsAppStatus] = useState<string | null>(null);

  // SMS Live Segment Calculator State
  const [calculatorText, setCalculatorText] = useState('');
  const [smsPreview, setSmsPreview] = useState<{
    segments: number;
    chars: number;
    is_unicode: boolean;
    max_single: number;
    concat_limit: number;
    cost_non_masking_bdt: number;
    cost_masking_bdt: number;
  } | null>(null);
  const [isCalculatingSms, setIsCalculatingSms] = useState(false);

  // Toggle Matrix Cell
  const handleToggle = (eventType: string, channel: string) => {
    setPreferences((prev) => ({
      ...prev,
      [eventType]: {
        ...prev[eventType],
        [channel]: !prev[eventType]?.[channel],
      },
    }));
  };

  // Save Preferences
  const handleSavePreferences = () => {
    startTransition(async () => {
      try {
        setSaveStatus('Saving...');
        const flatList: Array<{ event_type: string; channel: string; enabled: boolean }> = [];
        Object.entries(preferences).forEach(([ev, chMap]) => {
          Object.entries(chMap).forEach(([ch, enabled]) => {
            flatList.push({ event_type: ev, channel: ch, enabled });
          });
        });
        await updateAlertPreferences(flatList);
        setSaveStatus('Saved successfully!');
        setTimeout(() => setSaveStatus(null), 3000);
      } catch (err: any) {
        setSaveStatus(`Error: ${err.message || 'Failed to save'}`);
      }
    });
  };

  // Request Phone OTP
  const handleRequestOtp = async () => {
    if (!phoneNumberInput.trim()) {
      setOtpError('Please enter a valid Bangladesh phone number (e.g., 01712345678 or +8801712345678)');
      return;
    }
    setOtpError(null);
    setOtpSuccess(null);
    try {
      const res = await requestPhoneOtp(phoneNumberInput.trim());
      setIsOtpSent(true);
      setMaskedPhone(res.masked_phone);
      if ((res as any).dev_code) {
        setOtpCodeInput((res as any).dev_code);
        setOtpSuccess(`Code dispatched to ${res.masked_phone} (Sandbox Mock OTP: ${(res as any).dev_code} - auto-filled)`);
      } else {
        setOtpSuccess(`Verification code dispatched to ${res.masked_phone}`);
      }
      setCountdown(60);
      const timer = setInterval(() => {
        setCountdown((c) => {
          if (c <= 1) {
            clearInterval(timer);
            return 0;
          }
          return c - 1;
        });
      }, 1000);
    } catch (err: any) {
      setOtpError(err.message || 'Failed to send verification SMS');
    }
  };

  // Verify Phone OTP
  const handleVerifyOtp = async () => {
    if (!otpCodeInput.trim() || otpCodeInput.length !== 6) {
      setOtpError('Please enter the 6-digit code received via SMS.');
      return;
    }
    setOtpError(null);
    try {
      await verifyPhoneOtp(phoneNumberInput.trim(), otpCodeInput.trim());
      setOtpSuccess('Phone number verified successfully!');
      setIsOtpSent(false);
      setOtpCodeInput('');
      setPhoneNumberInput('');
      setChannels((prev) =>
        prev
          ? {
              ...prev,
              sms: {
                address: maskedPhone || '+8801XXXXXXXXX',
                verified: true,
                opted_out: false,
                locale: 'en',
              },
            }
          : null,
      );
    } catch (err: any) {
      setOtpError(err.message || 'Invalid or expired verification code.');
    }
  };

  // Opt In WhatsApp
  const handleWhatsAppOptIn = async () => {
    if (!channels?.sms?.verified) {
      setWhatsAppStatus('Please verify your phone number via SMS first.');
      return;
    }
    if (!whatsAppConsent) {
      setWhatsAppStatus('Please check the consent box to opt in.');
      return;
    }
    setWhatsAppStatus('Registering opt-in...');
    try {
      await optInWhatsApp(channels.sms.address || '');
      setWhatsAppStatus('Opted into WhatsApp compliance notifications!');
      setChannels((prev) =>
        prev
          ? {
              ...prev,
              whatsapp: {
                address: prev.sms?.address || '',
                verified: true,
                opted_in: true,
                opted_out: false,
              },
            }
          : null,
      );
    } catch (err: any) {
      setWhatsAppStatus(`Error: ${err.message}`);
    }
  };

  // Opt out of channel
  const handleChannelOptOut = async (channel: string) => {
    try {
      await optOutAlertChannel(channel);
      setChannels((prev) => {
        if (!prev) return null;
        if (channel === 'sms' && prev.sms) {
          return { ...prev, sms: { ...prev.sms, opted_out: true } };
        }
        if (channel === 'whatsapp' && prev.whatsapp) {
          return { ...prev, whatsapp: { ...prev.whatsapp, opted_out: true, opted_in: false } };
        }
        if (channel === 'email') {
          return { ...prev, email: { ...prev.email, opted_out: true } };
        }
        return prev;
      });
    } catch (err: any) {
      alert(`Failed to opt out: ${err.message}`);
    }
  };

  // Re-enable channel
  const handleChannelOptIn = async (channel: string) => {
    try {
      await reOptInAlertChannel(channel);
      setChannels((prev) => {
        if (!prev) return null;
        if (channel === 'sms' && prev.sms) {
          return { ...prev, sms: { ...prev.sms, opted_out: false } };
        }
        if (channel === 'whatsapp' && prev.whatsapp) {
          return { ...prev, whatsapp: { ...prev.whatsapp, opted_out: false, opted_in: true } };
        }
        if (channel === 'email') {
          return { ...prev, email: { ...prev.email, opted_out: false } };
        }
        return prev;
      });
    } catch (err: any) {
      alert(`Failed to re-enable channel: ${err.message}`);
    }
  };

  // SMS Live Calculator with instant response & BTRC validation
  const handleCalculateSms = async (text: string) => {
    setCalculatorText(text);
    if (!text) {
      setSmsPreview(null);
      return;
    }

    // Instant local calculation under BTRC standards
    const isUnicode = /[^\u0020-\u007E\u00A0-\u00FF\n\r]/.test(text);
    const chars = text.length;
    let segments = 1;
    if (isUnicode) {
      segments = chars <= 70 ? 1 : Math.ceil(chars / 67);
    } else {
      segments = chars <= 160 ? 1 : Math.ceil(chars / 153);
    }
    setSmsPreview({
      segments,
      chars,
      is_unicode: isUnicode,
      max_single: isUnicode ? 70 : 160,
      concat_limit: isUnicode ? 67 : 153,
      cost_non_masking_bdt: Math.round(segments * 0.35 * 100) / 100,
      cost_masking_bdt: Math.round(segments * 0.55 * 100) / 100,
    });

    setIsCalculatingSms(true);
    try {
      const res = await previewSmsSegments(text);
      if (res) setSmsPreview(res);
    } catch {
      // Local calculation already active
    } finally {
      setIsCalculatingSms(false);
    }
  };

  const eventsList = catalog.length > 0 ? catalog : Object.keys(EVENT_METADATA);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Bell className="w-6 h-6 text-indigo-600" />
          Notification Preferences & Matrix
        </h1>
        <p className="text-sm text-slate-600 mt-1">
          Configure your personal alert channels, verify emergency SMS/WhatsApp contacts, and control notification routing per event severity.
        </p>
      </div>

      {/* Grid: Channel Verification (Left) + SMS Live Segment Calculator (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contact Channel Verification Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">Contact Channels & Verification</h2>
                <p className="text-xs text-slate-500">Verified channels ensure regulatory alerts reach you promptly.</p>
              </div>
            </div>
          </div>

          {/* Email Channel */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mail className="w-5 h-5 text-slate-500" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-800">Email Alerts</span>
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-800">
                    Active
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{channels?.email?.address || 'user@example.com'}</p>
              </div>
            </div>
            {channels?.email?.opted_out ? (
              <button
                type="button"
                onClick={() => handleChannelOptIn('email')}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold transition-colors"
              >
                Re-enable
              </button>
            ) : (
              <button
                type="button"
                onClick={() => handleChannelOptOut('email')}
                className="text-xs text-slate-500 hover:text-rose-600 font-medium transition-colors"
              >
                Opt Out
              </button>
            )}
          </div>

          {/* SMS Channel */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Smartphone className="w-5 h-5 text-slate-500" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-800">SMS Alerts (Bangladesh)</span>
                    {channels?.sms?.verified ? (
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-800">
                        Verified
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-amber-100 text-amber-800">
                        Unverified
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">
                    {channels?.sms?.address || 'No phone number configured'}
                  </p>
                </div>
              </div>
              {channels?.sms?.verified && (
                channels.sms.opted_out ? (
                  <button
                    type="button"
                    onClick={() => handleChannelOptIn('sms')}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold transition-colors"
                  >
                    Re-enable
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleChannelOptOut('sms')}
                    className="text-xs text-slate-500 hover:text-rose-600 font-medium transition-colors"
                  >
                    Opt Out
                  </button>
                )
              )}
            </div>

            {/* OTP Verification Box if SMS not verified or updating */}
            {(!channels?.sms?.verified || channels?.sms?.opted_out) && (
              <div className="mt-3 pt-3 border-t border-slate-200/60 space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={phoneNumberInput}
                    onChange={(e) => setPhoneNumberInput(e.target.value)}
                    placeholder="+88017XXXXXXXX or 017XXXXXXXX"
                    className="flex-1 px-3 py-1.5 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={handleRequestOtp}
                    disabled={countdown > 0}
                    className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-all flex items-center gap-1.5"
                  >
                    <Send className="w-3 h-3" />
                    {countdown > 0 ? `Resend (${countdown}s)` : 'Send Code'}
                  </button>
                </div>

                {isOtpSent && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      maxLength={6}
                      value={otpCodeInput}
                      onChange={(e) => setOtpCodeInput(e.target.value)}
                      placeholder="6-digit OTP"
                      className="w-32 px-3 py-1.5 text-xs font-mono tracking-widest text-center rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <button
                      type="button"
                      onClick={handleVerifyOtp}
                      className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 transition-all flex items-center gap-1.5"
                    >
                      <Check className="w-3 h-3" />
                      Verify OTP
                    </button>
                  </div>
                )}

                {otpError && <p className="text-xs text-rose-600 font-medium">{otpError}</p>}
                {otpSuccess && <p className="text-xs text-emerald-600 font-medium">{otpSuccess}</p>}
              </div>
            )}
          </div>

          {/* WhatsApp Channel */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-emerald-600" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-800">WhatsApp Business</span>
                    {channels?.whatsapp?.opted_in ? (
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-800">
                        Opted In
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-slate-200 text-slate-700">
                        Not Opted In
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">
                    {channels?.whatsapp?.address || 'Requires verified phone number'}
                  </p>
                </div>
              </div>
              {channels?.whatsapp?.opted_in && (
                channels.whatsapp.opted_out ? (
                  <button
                    type="button"
                    onClick={() => handleChannelOptIn('whatsapp')}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold transition-colors"
                  >
                    Re-enable
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleChannelOptOut('whatsapp')}
                    className="text-xs text-slate-500 hover:text-rose-600 font-medium transition-colors"
                  >
                    Opt Out
                  </button>
                )
              )}
            </div>

            {/* Opt-in agreement if verified phone exists and not yet opted in */}
            {channels?.sms?.verified && !channels?.whatsapp?.opted_in && (
              <div className="mt-3 pt-3 border-t border-slate-200/60 space-y-2">
                <label className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={whatsAppConsent}
                    onChange={(e) => setWhatsAppConsent(e.target.checked)}
                    className="mt-0.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <span className="text-xs text-slate-600 leading-snug">
                    I explicitly consent to receive transactional Bangladesh compliance alerts and regulatory updates on WhatsApp via Meta Cloud API.
                  </span>
                </label>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={handleWhatsAppOptIn}
                    disabled={!whatsAppConsent}
                    className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-all flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Opt In to WhatsApp
                  </button>
                </div>
                {whatsAppStatus && (
                  <p className="text-xs font-medium text-slate-700">{whatsAppStatus}</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Live SMS Segment & Cost Calculator Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2.5 border-b border-slate-100 pb-4">
              <div className="p-2 rounded-xl bg-amber-50 text-amber-600">
                <Calculator className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">SMS Segment & Cost Estimator</h2>
                <p className="text-xs text-slate-500">Live BTRC / Operator Unicode segment counter (English vs বাংলা).</p>
              </div>
            </div>

            <p className="text-xs text-slate-600">
              Type or paste template text below to calculate characters, SMS segments, and per-message cost under Bangladesh telco standards (GSM-7: 160 chars; Unicode Bangla: 70 chars).
            </p>

            <textarea
              rows={4}
              value={calculatorText}
              onChange={(e) => handleCalculateSms(e.target.value)}
              placeholder="e.g.: NBR SRO No 245/2026 published. ভ্যাট দাখিল সংক্রান্ত নতুন নির্দেশনা কার্যকর।"
              className="w-full p-3 text-xs font-mono rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          {/* Results Grid */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            {smsPreview ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <div className="text-[10px] text-slate-500 uppercase font-semibold">Encoding</div>
                  <div className="text-xs font-bold text-slate-800 mt-0.5">
                    {smsPreview.is_unicode ? 'Unicode (বাংলা)' : 'GSM-7 (English)'}
                  </div>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <div className="text-[10px] text-slate-500 uppercase font-semibold">Characters</div>
                  <div className="text-xs font-bold text-slate-800 mt-0.5 font-mono">{smsPreview.chars}</div>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <div className="text-[10px] text-slate-500 uppercase font-semibold">Segments</div>
                  <div className="text-xs font-bold text-indigo-600 mt-0.5 font-mono">{smsPreview.segments}</div>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <div className="text-[10px] text-slate-500 uppercase font-semibold">Est. Cost (Masking)</div>
                  <div className="text-xs font-bold text-emerald-600 mt-0.5 font-mono">
                    ৳{smsPreview.cost_masking_bdt}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-xs text-slate-400">
                Type text in the box above to preview segments and cost.
              </div>
            )}
            <div className="text-[11px] text-slate-500">
              * Non-masking cost: ৳0.35/segment. Masking (LexGOV AI sender ID) cost: ৳0.55/segment. Single Unicode segment: 70 chars (concat: 67 chars/part).
            </div>
          </div>
        </div>
      </div>

      {/* Event Type x Channel Notification Matrix */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Event Delivery Matrix</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Specify which channels receive alerts for each category of compliance event.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {saveStatus && (
              <span className={`text-xs font-semibold ${saveStatus.includes('Error') ? 'text-rose-600' : 'text-emerald-600'}`}>
                {saveStatus}
              </span>
            )}
            <button
              type="button"
              onClick={handleSavePreferences}
              disabled={isPending}
              className="px-4 py-2 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-all flex items-center gap-2"
            >
              <Save className="w-3.5 h-3.5" />
              Save Preferences
            </button>
          </div>
        </div>

        {/* Matrix Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider">
                <th className="py-3 px-4">Event Type</th>
                <th className="py-3 px-4 text-center w-28">In-App</th>
                <th className="py-3 px-4 text-center w-28">Email</th>
                <th className="py-3 px-4 text-center w-28">SMS</th>
                <th className="py-3 px-4 text-center w-28">WhatsApp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {eventsList.map((ev) => {
                const meta = EVENT_METADATA[ev] || {
                  label: ev.replace(/_/g, ' '),
                  description: 'Compliance event',
                  category: 'General',
                };
                const userCh = preferences[ev] || { in_app: true, email: true, sms: false, whatsapp: false };

                return (
                  <tr key={ev} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-800">{meta.label}</div>
                      <div className="text-[11px] text-slate-500 mt-0.5">{meta.description}</div>
                      <span className="inline-block mt-1 text-[10px] px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md font-medium">
                        {meta.category}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <input
                        type="checkbox"
                        checked={userCh.in_app}
                        onChange={() => handleToggle(ev, 'in_app')}
                        className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                    </td>
                    <td className="py-3 px-4 text-center">
                      <input
                        type="checkbox"
                        checked={userCh.email}
                        onChange={() => handleToggle(ev, 'email')}
                        className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                    </td>
                    <td className="py-3 px-4 text-center">
                      <input
                        type="checkbox"
                        checked={userCh.sms}
                        onChange={() => handleToggle(ev, 'sms')}
                        className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                    </td>
                    <td className="py-3 px-4 text-center">
                      <input
                        type="checkbox"
                        checked={userCh.whatsapp}
                        onChange={() => handleToggle(ev, 'whatsapp')}
                        className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
