'use client';
import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Shield, FileText, Cpu, CheckCircle2, ArrowRight, BarChart3 } from 'lucide-react';

export const Navbar = () => {
  const pathname = usePathname();

  const navLinks = [
    { href: '/', label: 'Overview', icon: BarChart3 },
    { href: '/upload', label: 'SOP Ingestion', icon: FileText },
    { href: '/regulations', label: 'Watcher Diff', icon: Shield },
    { href: '/analysis', label: 'Agent Pipeline', icon: Cpu },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/90 border-b border-slate-200/80 backdrop-blur-md shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-xl bg-emerald-600/10 border border-emerald-500/20 flex items-center justify-center text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-all shadow-2xs">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-extrabold text-slate-900 tracking-tight">Compliance<span className="text-emerald-600">OS</span></span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono border border-slate-200 font-semibold">ENTERPRISE</span>
            </div>
            <p className="text-[10px] text-slate-500 -mt-0.5 font-medium">Regulatory Intelligence System</p>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
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
        </nav>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>NBR VAT 2025 Standard</span>
          </div>

          <Link
            href="/upload"
            className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-all flex items-center gap-1.5 shadow-sm"
          >
            <span>Run Audit</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

      </div>
    </header>
  );
};
