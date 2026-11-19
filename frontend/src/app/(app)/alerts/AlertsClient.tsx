'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Bell,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  Clock,
  ExternalLink,
  ChevronRight,
  Filter,
  Send,
  MessageSquare,
  Mail,
  Smartphone,
  Eye,
  Settings,
  Sliders,
  Check,
} from 'lucide-react';
import { AlertItem, AlertDeliveryItem, acknowledgeAlert, getAlertDeliveries } from '@/lib/api';

interface AlertsClientProps {
  initialAlerts: AlertItem[];
  userRole: string;
  channelsData: any;
  currentParams: { status?: string; severity?: string };
}

export function AlertsClient({
  initialAlerts,
  userRole,
  channelsData,
  currentParams,
}: AlertsClientProps) {
  const router = useRouter();
  const [alerts, setAlerts] = useState<AlertItem[]>(initialAlerts);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [deliveries, setDeliveries] = useState<AlertDeliveryItem[]>([]);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);
  const [ackingId, setAckingId] = useState<string | null>(null);

  const handleAcknowledge = async (alertId: string) => {
    setAckingId(alertId);
    try {
      const res = await acknowledgeAlert(alertId, 'in_app');
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status: 'acknowledged', acked_at: new Date().toISOString() } : a))
      );
      if (selectedAlert && selectedAlert.id === alertId) {
        setSelectedAlert((prev) => (prev ? { ...prev, status: 'acknowledged', acked_at: new Date().toISOString() } : null));
      }
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    } finally {
      setAckingId(null);
    }
  };

  const openDeliveryAudit = async (alert: AlertItem) => {
    setSelectedAlert(alert);
    setLoadingDeliveries(true);
    try {
      const res = await getAlertDeliveries(alert.id);
      setDeliveries(res.deliveries || []);
    } catch (err) {
      console.error('Failed to load deliveries:', err);
      setDeliveries([]);
    } finally {
      setLoadingDeliveries(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'high':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'medium':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'acknowledged':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'escalated':
        return 'bg-rose-100 text-rose-800 border-rose-300 font-bold';
      case 'held':
        return 'bg-sky-100 text-sky-800 border-sky-200';
      case 'sent':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-3xl bg-slate-900 text-white shadow-sm">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-semibold">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Multi-Channel Compliance Notification Center</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-black tracking-tight">Alert Center</h1>
          <p className="text-xs sm:text-sm text-slate-300 max-w-2xl leading-relaxed">
            Severity-aware notification routing for Bangladeshi SMEs. Connect your email, verified mobile SMS, and WhatsApp to never miss a regulatory gazette change or compliance filing deadline.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/settings/notifications"
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold flex items-center gap-1.5 transition-all border border-slate-700"
          >
            <Settings className="w-4 h-4 text-emerald-400" />
            <span>Preferences</span>
          </Link>
          {['owner', 'admin'].includes(userRole) && (
            <Link
              href="/settings/alert-routing"
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs"
            >
              <Sliders className="w-4 h-4" />
              <span>Routing Rules</span>
            </Link>
          )}
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-white border border-slate-200/90 shadow-2xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 mr-2 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Filter by:
          </span>

          {['all', 'critical', 'high', 'medium', 'low'].map((sev) => {
            const isActive = (currentParams.severity || 'all') === sev;
            return (
              <button
                key={sev}
                onClick={() => {
                  const url = new URL(window.location.href);
                  if (sev === 'all') url.searchParams.delete('severity');
                  else url.searchParams.set('severity', sev);
                  router.push(url.pathname + url.search);
                }}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition-all ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                }`}
              >
                {sev}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
          <span>{alerts.length} alerts in workspace</span>
        </div>
      </div>

      {/* Main Alert List Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          {alerts.length === 0 ? (
            <div className="p-12 text-center rounded-3xl bg-white border border-slate-200/90 space-y-3">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
              <h3 className="text-base font-bold text-slate-900">All clear! No alerts matching filter</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                No high-risk regulatory updates, impending deadlines, or overdue acknowledgments detected for this filter.
              </p>
            </div>
          ) : (
            alerts.map((alert) => {
              const isAcked = alert.status === 'acknowledged';
              const isEscalated = alert.status === 'escalated';
              const p = alert.event_payload || {};

              return (
                <div
                  key={alert.id}
                  className={`p-5 rounded-2xl bg-white border transition-all shadow-2xs hover:shadow-sm space-y-3 ${
                    isEscalated ? 'border-rose-300 bg-rose-50/20' : 'border-slate-200/90'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${getSeverityBadge(alert.severity)}`}>
                        {alert.severity}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${getStatusBadge(alert.status)}`}>
                        {alert.status.replace('_', ' ')}
                      </span>
                      {alert.escalation_level > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-600 text-white shadow-2xs">
                          Escalation Lvl {alert.escalation_level}
                        </span>
                      )}
                    </div>

                    <span className="text-[11px] text-slate-600 font-mono">
                      {new Date(alert.created_at).toLocaleString('en-GB', { timeZone: 'Asia/Dhaka' })} BST
                    </span>
                  </div>

                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      {p.law_title || p.finding_title || p.title || alert.event_type.replace(/_/g, ' ').toUpperCase()}
                    </h3>
                    <p className="text-xs text-slate-600 mt-1 line-clamp-2 leading-relaxed">
                      {p.summary || p.document_title || 'Compliance notification detected by monitoring agent.'}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      {p.domain_tag && (
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium text-[11px]">
                          #{p.domain_tag}
                        </span>
                      )}
                      <span>Recipient: {alert.recipient_name || alert.recipient_email || 'Compliance Officer'}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openDeliveryAudit(alert)}
                        className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold flex items-center gap-1 transition-all"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Audit Log</span>
                      </button>

                      {alert.ack_required && !isAcked && (
                        <button
                          onClick={() => handleAcknowledge(alert.id)}
                          disabled={ackingId === alert.id}
                          className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1 shadow-xs transition-all disabled:opacity-50"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>{ackingId === alert.id ? 'Acknowledging...' : 'Acknowledge'}</span>
                        </button>
                      )}

                      {p.link && (
                        <Link
                          href={p.link}
                          className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold flex items-center gap-1 transition-all"
                        >
                          <span>View Detail</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Sidebar: Delivery Audit & Channel Health */}
        <div className="space-y-6">
          {/* Quick Channels Health Widget */}
          <div className="p-5 rounded-3xl bg-white border border-slate-200/90 shadow-2xs space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Your Communication Channels</h3>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4 text-indigo-600" />
                  <div>
                    <div className="font-semibold text-slate-800">Email Address</div>
                    <div className="text-[11px] text-slate-600">{channelsData?.email?.address || 'Configured'}</div>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">Active</span>
              </div>

              <div className="flex items-center justify-between text-xs p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2">
                  <Smartphone className="w-4 h-4 text-emerald-600" />
                  <div>
                    <div className="font-semibold text-slate-800">SMS Mobile (OTP)</div>
                    <div className="text-[11px] text-slate-600">{channelsData?.sms?.address || 'Not verified'}</div>
                  </div>
                </div>
                {channelsData?.sms?.verified ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">Verified</span>
                ) : (
                  <Link href="/settings/notifications" className="text-[11px] text-indigo-600 font-bold hover:underline">
                    Verify
                  </Link>
                )}
              </div>

              <div className="flex items-center justify-between text-xs p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-emerald-500" />
                  <div>
                    <div className="font-semibold text-slate-800">WhatsApp Business</div>
                    <div className="text-[11px] text-slate-600">{channelsData?.whatsapp?.opted_in ? 'Opted in' : 'Opt-in needed'}</div>
                  </div>
                </div>
                {channelsData?.whatsapp?.opted_in ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">Opted In</span>
                ) : (
                  <Link href="/settings/notifications" className="text-[11px] text-indigo-600 font-bold hover:underline">
                    Opt In
                  </Link>
                )}
              </div>
            </div>
          </div>

          {/* Selected Alert Delivery Attempt Logs */}
          {selectedAlert && (
            <div className="p-5 rounded-3xl bg-white border border-slate-200/90 shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Delivery Audit Trail</h3>
                <button
                  onClick={() => setSelectedAlert(null)}
                  className="text-xs text-slate-600 hover:text-slate-800 font-bold"
                >
                  Close
                </button>
              </div>

              <div className="text-xs text-slate-600">
                <span className="font-semibold text-slate-900">Alert ID:</span> {selectedAlert.id}
              </div>

              {loadingDeliveries ? (
                <div className="py-6 text-center text-xs text-slate-600">Loading delivery records...</div>
              ) : deliveries.length === 0 ? (
                <div className="py-6 text-center text-xs text-slate-600">No delivery attempts recorded yet.</div>
              ) : (
                <div className="space-y-2">
                  {deliveries.map((del) => (
                    <div key={del.id} className="p-3 rounded-2xl bg-slate-50 border border-slate-100 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800 uppercase text-[11px]">{del.channel} ({del.provider})</span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          del.status === 'delivered' ? 'bg-emerald-100 text-emerald-800' :
                          del.status === 'sent' ? 'bg-indigo-100 text-indigo-800' :
                          'bg-rose-100 text-rose-800'
                        }`}>
                          {del.status}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-600">
                        Attempt {del.attempt} • Segments: {del.segments} • Cost: {del.cost_estimate} BDT
                      </div>
                      {del.error_code && (
                        <div className="text-[11px] text-rose-600 font-mono">{del.error_code}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
