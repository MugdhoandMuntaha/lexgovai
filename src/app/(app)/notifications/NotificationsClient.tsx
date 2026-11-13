'use client';

import React, { useState, useTransition } from 'react';
import Link from 'next/link';
import { Bell, CheckCheck, Clock, ExternalLink, ShieldAlert, Check } from 'lucide-react';
import { markAllNotificationsRead, markNotificationRead } from '@/lib/api';
import { NotificationItem } from '@/lib/types';
import { setUnreadCount } from '@/lib/notificationStore';

interface Props {
  initialNotifications: NotificationItem[];
  initialUnreadCount: number;
}

export function NotificationsClient({ initialNotifications, initialUnreadCount }: Props) {
  const [items, setItems] = useState<NotificationItem[]>(initialNotifications);
  const [unread, setUnread] = useState(initialUnreadCount);
  const [isPending, startTransition] = useTransition();

  const handleMarkOne = (id: string) => {
    startTransition(async () => {
      try {
        await markNotificationRead(id);
        setItems((prev) =>
          prev.map((item) => (item.id === id ? { ...item, read_at: new Date().toISOString() } : item))
        );
        setUnread((prev) => {
          const next = Math.max(0, prev - 1);
          setUnreadCount(next);
          return next;
        });
      } catch (err) {
        console.error('Failed to mark read', err);
      }
    });
  };

  const handleMarkAll = () => {
    startTransition(async () => {
      try {
        await markAllNotificationsRead();
        setItems((prev) =>
          prev.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() }))
        );
        setUnread(0);
        setUnreadCount(0);
      } catch (err) {
        console.error('Failed to mark all read', err);
      }
    });
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Notification Center</h1>
            {unread > 0 && (
              <span className="px-2.5 py-0.5 rounded-full bg-rose-500 text-white text-xs font-bold shadow-xs">
                {unread} unread
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Real-time compliance alerts, statutory deadline reminders, and workspace activity.
          </p>
        </div>

        {unread > 0 && (
          <button
            type="button"
            onClick={handleMarkAll}
            disabled={isPending}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-all border border-slate-200"
          >
            <CheckCheck className="w-4 h-4 text-emerald-600" />
            <span>Mark all as read</span>
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-300">
          <Bell className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <p className="text-sm font-semibold text-slate-700">No Notifications</p>
          <p className="text-xs text-slate-500 mt-1">
            You are all caught up! New alerts and regulatory updates will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const isRead = Boolean(item.read_at);
            return (
              <div
                key={item.id}
                className={`p-4 rounded-2xl border transition-all flex items-start justify-between gap-4 ${
                  isRead
                    ? 'bg-white border-slate-200/80 opacity-85'
                    : 'bg-emerald-50/30 border-emerald-200 shadow-xs'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 p-2 rounded-xl ${
                      isRead ? 'bg-slate-100 text-slate-500' : 'bg-emerald-100 text-emerald-700'
                    }`}
                  >
                    <ShieldAlert className="w-4 h-4" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className={`text-sm ${isRead ? 'font-semibold text-slate-800' : 'font-bold text-slate-900'}`}>
                        {item.title}
                      </h4>
                      {!isRead && (
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      )}
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">{item.body}</p>
                    <div className="flex items-center gap-3 pt-1 text-[11px] text-slate-400 font-mono">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(item.created_at).toLocaleString('en-GB', {
                          day: 'numeric',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                      {item.link && (
                        <Link
                          href={item.link}
                          className="flex items-center gap-1 text-emerald-600 hover:text-emerald-700 font-medium"
                        >
                          <span>Open action</span>
                          <ExternalLink className="w-3 h-3" />
                        </Link>
                      )}
                    </div>
                  </div>
                </div>

                {!isRead && (
                  <button
                    type="button"
                    onClick={() => handleMarkOne(item.id)}
                    title="Mark as read"
                    className="p-1.5 rounded-lg border border-slate-200 hover:bg-white text-slate-500 hover:text-emerald-600 transition-colors shrink-0"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
