import React from 'react';
import { AlertTriangle } from 'lucide-react';

export const LegalDisclaimer: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  if (compact) {
    return (
      <div className="flex items-center gap-2 text-xs text-amber-400/90 bg-amber-950/40 border border-amber-500/30 px-3 py-1.5 rounded-lg">
        <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-400" />
        <span>This is not legal advice. Verify with a licensed professional before acting.</span>
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-900/80 border border-amber-500/30 rounded-xl p-4 shadow-lg backdrop-blur-md text-amber-200/90 text-sm flex items-start gap-3 my-6">
      <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400 shrink-0">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <div>
        <h5 className="font-semibold text-amber-300 text-sm mb-0.5">Important Disclaimer</h5>
        <p className="text-xs text-amber-200/80 leading-relaxed">
          ComplianceOS provides AI-assisted document analysis and comparative insights. <strong>This is not legal advice.</strong> Always verify all regulatory findings and redline policy drafts with a licensed legal or tax professional before implementation.
        </p>
      </div>
    </div>
  );
};
