import React from 'react';
import { AlertCircle } from 'lucide-react';

interface LegalDisclaimerProps {
  compact?: boolean;
}

export const LegalDisclaimer: React.FC<LegalDisclaimerProps> = ({ compact = false }) => {
  if (compact) {
    return (
      <div className="p-3 rounded-xl bg-amber-50/80 border border-amber-200 text-amber-900 text-xs flex items-center gap-2">
        <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
        <span className="font-medium">
          <strong className="text-amber-800">Notice:</strong> Automated analysis output. Verify all legal findings with certified VAT compliance counsel.
        </span>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-2xl bg-amber-50/70 border border-amber-200/80 text-amber-950 text-xs space-y-1.5 shadow-2xs">
      <div className="flex items-center gap-2 text-amber-800 font-bold text-xs uppercase tracking-wider">
        <AlertCircle className="w-4 h-4 text-amber-600" />
        <span>Mandatory Regulatory & Legal Disclaimer</span>
      </div>
      <p className="leading-relaxed text-amber-900 font-medium">
        ComplianceOS provides automated multi-agent AI analysis comparing corporate SOP documentation against government regulatory amendments. All outputs, risk scores, redlined policy drafts, and technical recommendations are generated for informational assistance only and <strong className="text-amber-950 font-semibold">do not constitute legal advice</strong>. Formal compliance decisions must be reviewed by licensed legal counsel or accredited VAT tax practitioners.
      </p>
    </div>
  );
};
