'use client';

import React, { useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Shield,
  User,
  LogOut,
  Menu,
  X,
  Bell,
  Settings,
  Lock,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { PlanBadge } from './PlanBadge';
import { AppsMenu } from './AppsMenu';
import { primaryNavItems, navItems } from '@/lib/navItems';
import {
  subscribeNotifications,
  getUnreadSnapshot,
  getUnreadServerSnapshot,
} from '@/lib/notificationStore';

export const Navbar = () => {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { user, subscription, logout, isLoading, hasCapability, openUpgradeModal } = useAuth();
  const unreadCount = useSyncExternalStore(
    subscribeNotifications,
    getUnreadSnapshot,
    getUnreadServerSnapshot
  );

  // Filter mobile items for platform admin visibility
  const mobileNavItems = navItems.filter((item) => {
    if (item.adminOnly && !user?.is_platform_admin) {
      return false;
    }
    return true;
  });

  return (
    <header className="sticky top-0 z-50 bg-white/90 border-b border-slate-200/80 backdrop-blur-md shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo / Brand */}
        <Link href="/" className="flex items-center gap-3 group shrink-0">
          <div className="w-9 h-9 rounded-xl bg-emerald-600/10 border border-emerald-500/20 flex items-center justify-center text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-all shadow-2xs">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-extrabold text-slate-900 tracking-tight">
                Compliance<span className="text-emerald-600">OS</span>
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono border border-slate-200 font-semibold">
                ENTERPRISE
              </span>
            </div>
            <p className="text-[10px] text-slate-500 -mt-0.5 font-medium">Regulatory Intelligence System</p>
          </div>
        </Link>

        {/* Desktop Primary Navigation (5 Most Useful Links + 3-Dot Apps Popup) */}
        <nav className="hidden md:flex items-center gap-1.5 ml-4">
          {primaryNavItems.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  isActive
                    ? 'bg-slate-100 text-slate-900 border border-slate-200 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Icon className="w-3.5 h-3.5 text-slate-500" />
                <span>{link.label}</span>
              </Link>
            );
          })}

          {/* 3-Dot All Features Menu */}
          <AppsMenu unreadCount={unreadCount} />
        </nav>

        {/* User / Auth status */}
        <div className="hidden sm:flex items-center gap-2">
          {!isLoading && user ? (
            <Link
              href="/notifications"
              title="Notifications"
              aria-label={`Notifications ${unreadCount > 0 ? `(${unreadCount} unread)` : ''}`}
              className={`relative p-2 rounded-xl border transition-all ${
                pathname === '/notifications'
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'border-slate-200 text-slate-700 hover:bg-slate-100'
              }`}
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow-xs">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </Link>
          ) : !isLoading ? (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-all"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all shadow-xs"
              >
                Get Started
              </Link>
            </div>
          ) : null}
        </div>

        {/* Mobile menu toggle */}
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          aria-label="Toggle navigation"
          className="md:hidden p-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50"
        >
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile drawer (single source of truth via navItems) */}
      {open && (
        <nav className="md:hidden border-t border-slate-200 bg-white px-4 py-3 space-y-1 max-h-[calc(100vh-4.5rem)] overflow-y-auto">
          {mobileNavItems.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            const isGated = Boolean(link.capability && !hasCapability(link.capability));

            if (isGated) {
              return (
                <button
                  key={link.href}
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    openUpgradeModal(link.label, 'starter');
                  }}
                  className="w-full px-3 py-2 rounded-xl text-xs font-semibold flex items-center justify-between text-slate-500 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-slate-400" />
                    <span>{link.label}</span>
                  </div>
                  <Lock className="w-3.5 h-3.5 text-amber-500" />
                </button>
              );
            }

            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center justify-between transition-colors ${
                  isActive ? 'bg-slate-100 text-slate-900 font-bold' : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4 text-slate-500" />
                  <span>{link.label}</span>
                </div>
                {link.href === '/notifications' && unreadCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
                    {unreadCount}
                  </span>
                )}
              </Link>
            );
          })}

          <div className="pt-3 border-t border-slate-100">
            {user ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between px-3 py-1 text-xs">
                  <span className="text-slate-500">{user.email}</span>
                  <PlanBadge planId={subscription?.plan_id} size="sm" />
                </div>
                <Link
                  href="/notifications"
                  onClick={() => setOpen(false)}
                  className="w-full px-4 py-2 rounded-xl bg-slate-50 text-slate-800 text-xs font-semibold flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <Bell className="w-4 h-4 text-slate-500" />
                    <span>Notifications</span>
                  </div>
                  {unreadCount > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
                      {unreadCount}
                    </span>
                  )}
                </Link>
                {user.is_platform_admin && (
                  <Link
                    href="/admin"
                    onClick={() => setOpen(false)}
                    className="w-full px-4 py-2 rounded-xl bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold flex items-center gap-2"
                  >
                    <Settings className="w-4 h-4" />
                    <span>Admin Console</span>
                  </Link>
                )}
                <Link
                  href="/account"
                  onClick={() => setOpen(false)}
                  className="w-full px-4 py-2 rounded-xl bg-slate-100 text-slate-900 text-xs font-semibold flex items-center justify-center gap-1.5"
                >
                  <User className="w-4 h-4" />
                  <span>Account & Usage</span>
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    logout();
                  }}
                  className="w-full px-4 py-2 rounded-xl border border-rose-200 text-rose-600 text-xs font-semibold flex items-center justify-center gap-1.5"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <Link
                  href="/login"
                  onClick={() => setOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-700 text-xs font-semibold text-center"
                >
                  Sign In
                </Link>
                <Link
                  href="/signup"
                  onClick={() => setOpen(false)}
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold text-center"
                >
                  Get Started
                </Link>
              </div>
            )}
          </div>
        </nav>
      )}
    </header>
  );
};
