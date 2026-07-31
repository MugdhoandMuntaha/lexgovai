import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Navbar } from '@/components/Navbar';
import { LegalDisclaimer } from '@/components/LegalDisclaimer';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'ComplianceOS | AI Compliance Action Plan Dashboard',
  description: 'AI-powered compliance dashboard comparing regulatory changes against corporate SOPs using multi-agent RAG pipeline.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-slate-50 text-slate-900 min-h-screen flex flex-col antialiased selection:bg-emerald-500 selection:text-white`}>
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <footer className="border-t border-slate-200/80 bg-white py-6">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
            <div>© 2026 ComplianceOS Technologies Inc. Designed for Bangladeshi SME Compliance.</div>
            <LegalDisclaimer compact />
          </div>
        </footer>
      </body>
    </html>
  );
}
