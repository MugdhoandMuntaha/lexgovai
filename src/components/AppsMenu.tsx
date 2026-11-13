'use client';

import React, { useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MoreHorizontal, Lock, X, User, Settings, LogOut } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { PlanBadge } from './PlanBadge';
import { navItems } from '@/lib/navItems';

interface AppsMenuProps {
  unreadCount?: number;
}

const itemColorMap: Record<string, { bg: string; text: string }> = {
  '/': { bg: 'bg-slate-100', text: 'text-slate-700' },
  '/upload': { bg: 'bg-emerald-50', text: 'text-emerald-700' },
  '/regulations': { bg: 'bg-blue-50', text: 'text-blue-700' },
  '/analysis': { bg: 'bg-violet-50', text: 'text-violet-700' },
  '/assistant': { bg: 'bg-teal-50', text: 'text-teal-700' },
  '/monitoring': { bg: 'bg-amber-50', text: 'text-amber-700' },
  '/news': { bg: 'bg-sky-50', text: 'text-sky-700' },
  '/notifications': { bg: 'bg-rose-50', text: 'text-rose-700' },
  '/team': { bg: 'bg-indigo-50', text: 'text-indigo-700' },
  '/settings/api-keys': { bg: 'bg-orange-50', text: 'text-orange-700' },
  '/support': { bg: 'bg-pink-50', text: 'text-pink-700' },
  '/pricing': { bg: 'bg-emerald-50', text: 'text-emerald-700' },
  '/account': { bg: 'bg-slate-100', text: 'text-slate-700' },
  '/admin': { bg: 'bg-purple-50', text: 'text-purple-700' },
  '/laws': { bg: 'bg-indigo-50', text: 'text-indigo-700' },
};

export function AppsMenu({ unreadCount = 0 }: AppsMenuProps) {
  const pathname = usePathname();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  const { user, subscription, logout, hasCapability, openUpgradeModal } = useAuth();

  const handleOpen = () => {
    if (dialogRef.current && !dialogRef.current.open) {
      dialogRef.current.showModal();
      setIsOpen(true);
    }
  };

  const handleClose = () => {
    if (dialogRef.current && dialogRef.current.open) {
      dialogRef.current.close();
    }
  };

  const onDialogClose = () => {
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  // Filter items: show admin only if platform admin
  const visibleItems = navItems.filter((item) => {
    if (item.adminOnly && !user?.is_platform_admin) {
      return false;
    }
    return true;
  });

  return (
    <div className="relative inline-block">
      {/* 3-Dot Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        onClick={handleOpen}
        aria-label="All features"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        title="All features & apps"
        className={`p-2 rounded-xl border transition-all flex items-center justify-center ${
          isOpen
            ? 'bg-slate-900 text-white border-slate-900 shadow-2xs'
            : 'border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-100'
        }`}
      >
        <MoreHorizontal className="w-4 h-4" />
      </button>

      {/* Native <dialog> Modal / Anchored Panel */}
      <dialog
        ref={dialogRef}
        onClose={onDialogClose}
        onClick={(e) => {
          // Close on backdrop click (dialog element itself is the backdrop target)
          if (e.target === dialogRef.current) {
            handleClose();
          }
        }}
        className="backdrop:bg-slate-900/30 backdrop:backdrop-blur-xs fixed top-16 right-4 sm:right-8 md:right-16 m-0 p-0 rounded-3xl bg-white border border-slate-200/90 shadow-2xl text-slate-900 focus:outline-none z-50 w-[380px] max-w-[calc(100vw-2rem)] overflow-hidden"
      >
        <div className="p-4 sm:p-5 max-h-[85vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3.5">
            <div>
              <h3 className="text-sm font-bold text-slate-900">All Features & Apps</h3>
              <p className="text-[11px] text-slate-500">ComplianceOS Platform Modules</p>
            </div>
            <button
              type="button"
              onClick={handleClose}
              aria-label="Close menu"
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* User Account & Actions (Admin, PlanBadge, User, LogOut) */}
          {user && (
            <div className="p-2.5 bg-slate-50/90 rounded-2xl border border-slate-200/80 mb-4 flex items-center justify-between gap-1.5 shadow-2xs">
              <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                {user.is_platform_admin && (
                  <Link
                    href="/admin"
                    onClick={handleClose}
                    title="Platform Administration"
                    className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 border transition-all shadow-2xs ${
                      pathname.startsWith('/admin')
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'border-indigo-200 text-indigo-700 bg-indigo-50/70 hover:bg-indigo-100'
                    }`}
                  >
                    <Settings className="w-3.5 h-3.5" />
                    <span>Admin</span>
                  </Link>
                )}

                <div onClick={handleClose} className="cursor-pointer shrink-0">
                  <PlanBadge planId={subscription?.plan_id} size="sm" />
                </div>

                <Link
                  href="/account"
                  onClick={handleClose}
                  title="Account & Usage Settings"
                  className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 border transition-all ${
                    pathname === '/account'
                      ? 'bg-slate-900 text-white border-slate-900'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100 shadow-2xs'
                  }`}
                >
                  <User className="w-3.5 h-3.5 text-slate-500" />
                  <span className="truncate max-w-[85px]">{user.email.split('@')[0]}</span>
                </Link>
              </div>

              <button
                type="button"
                onClick={() => {
                  handleClose();
                  logout();
                }}
                title="Log out"
                aria-label="Log out"
                className="p-1.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-all shadow-2xs shrink-0"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Grid of Circular App Icons */}
          <div className="grid grid-cols-3 gap-y-4 gap-x-2">
            {visibleItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              const colors = itemColorMap[item.href] || { bg: 'bg-slate-100', text: 'text-slate-700' };

              // Check capability gating
              const isGated = Boolean(item.capability && !hasCapability(item.capability));
              const isNotifications = item.href === '/notifications';

              const content = (
                <div className="flex flex-col items-center text-center group cursor-pointer focus:outline-none">
                  <div
                    className={`relative w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-2xs group-hover:scale-105 ${colors.bg} ${colors.text} ${
                      isActive
                        ? 'ring-2 ring-emerald-600 ring-offset-2'
                        : 'group-hover:ring-2 group-hover:ring-slate-300'
                    }`}
                  >
                    <Icon className="w-6 h-6" />

                    {/* Lock badge if feature is gated by subscription */}
                    {isGated && (
                      <span
                        title="Upgrade to unlock"
                        className="absolute -top-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-white shadow-xs border-2 border-white"
                      >
                        <Lock className="w-2.5 h-2.5" />
                      </span>
                    )}

                    {/* Unread badge for notifications */}
                    {isNotifications && unreadCount > 0 && (
                      <span className="absolute -top-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-rose-500 text-white text-[10px] font-bold shadow-xs border-2 border-white">
                        {unreadCount > 9 ? '9+' : unreadCount}
                      </span>
                    )}
                  </div>
                  <span
                    className={`mt-1.5 text-xs text-center line-clamp-2 max-w-[84px] leading-tight transition-colors ${
                      isActive ? 'font-bold text-emerald-800' : 'text-slate-700 group-hover:text-slate-900 font-medium'
                    }`}
                  >
                    {item.label}
                  </span>
                </div>
              );

              if (isGated) {
                return (
                  <button
                    key={item.href}
                    type="button"
                    onClick={() => {
                      handleClose();
                      openUpgradeModal(item.label, 'starter');
                    }}
                    className="focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-xl"
                  >
                    {content}
                  </button>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={handleClose}
                  className="focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-xl"
                >
                  {content}
                </Link>
              );
            })}
          </div>
        </div>
      </dialog>
    </div>
  );
}
