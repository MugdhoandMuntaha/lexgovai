'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  FileText,
  RefreshCw,
  Building2,
} from 'lucide-react';
import {
  StarterAnswers,
  StarterGuideResponse,
  StarterPolicyItem,
  PolicyTier,
  DocumentUploadResponse,
} from '@/lib/types';
import { getStarterGuide, createStarterSOP } from '@/lib/api';
import {
  loadStarterAnswers,
  saveStarterAnswers,
  loadStarterStep,
  saveStarterStep,
  saveWorkspace,
} from '@/lib/session';
import { LegalDisclaimer } from './LegalDisclaimer';

interface QuestionConfig<K extends keyof StarterAnswers> {
  key: K;
  title: string;
  subtitle: string;
  options: { value: StarterAnswers[K]; label: string; desc?: string }[];
}

const QUESTIONS: [
  QuestionConfig<'stage'>,
  QuestionConfig<'sector'>,
  QuestionConfig<'jurisdiction'>,
  QuestionConfig<'customers'>,
  QuestionConfig<'delivery'>,
  QuestionConfig<'hiring'>,
  QuestionConfig<'collects_data'>,
  QuestionConfig<'payments'>,
  QuestionConfig<'first_help'>,
] = [
  {
    key: 'stage',
    title: 'What stage is your business at?',
    subtitle: 'Helps us prioritize immediate launch essentials vs operational governance.',
    options: [
      { value: 'exploring_idea', label: "I'm exploring a business idea", desc: 'Evaluating concepts, feasibility, and requirements' },
      { value: 'planning_launch', label: "I'm planning to launch soon", desc: 'Finalizing structure, licenses, and initial setup' },
      { value: 'recently_started', label: "I've recently started", desc: 'Operating within the first year of business' },
      { value: 'operating', label: 'My business is already operating', desc: 'Established trade with active daily transactions' },
    ],
  },
  {
    key: 'sector',
    title: 'Which sector best describes your business?',
    subtitle: 'Tailors policies for commercial, digital, production, or service activities.',
    options: [
      { value: 'retail', label: 'Retail / physical shop', desc: 'Storefront sales, inventory, physical checkout' },
      { value: 'ecommerce', label: 'E-commerce / online business', desc: 'Online storefront, marketplace, direct-to-consumer delivery' },
      { value: 'software_it', label: 'Software / IT services', desc: 'Software development, SaaS, IT consulting, cloud services' },
      { value: 'food_restaurant', label: 'Food / restaurant', desc: 'Cafes, catering, cloud kitchens, food manufacturing' },
      { value: 'manufacturing', label: 'Manufacturing / production', desc: 'Raw material processing, workshops, factory assembly' },
      { value: 'professional_services', label: 'Professional services / consulting', desc: 'Legal, accounting, marketing, engineering advice' },
      { value: 'financial_fintech', label: 'Financial services / fintech', desc: 'Payments, microfinance, wallets, lending' },
      { value: 'other', label: 'Other', desc: 'General trade or commercial activities' },
    ],
  },
  {
    key: 'jurisdiction',
    title: 'Where will your business operate?',
    subtitle: 'ComplianceOS benchmarks directly against National Board of Revenue (NBR) standards for Bangladesh.',
    options: [
      { value: 'bangladesh', label: 'Bangladesh', desc: 'Subject to Bangladesh trade licenses, NBR VAT, and labor laws' },
      { value: 'international', label: 'International / multiple countries', desc: 'Cross-border trade across multiple regional jurisdictions' },
      { value: 'other_country', label: 'Another country', desc: 'Operating in a specific jurisdiction outside Bangladesh' },
    ],
  },
  {
    key: 'customers',
    title: 'Who will your customers be?',
    subtitle: 'Determines consumer protection vs corporate contract requirements.',
    options: [
      { value: 'b2c', label: 'Individual customers (B2C)', desc: 'Retail sales, subscriptions, direct consumer orders' },
      { value: 'b2b', label: 'Other businesses (B2B)', desc: 'Corporate clients, vendor contracts, wholesale' },
      { value: 'both', label: 'Both', desc: 'Serving both individual consumers and corporate entities' },
      { value: 'undecided', label: 'Not decided yet', desc: 'Business model is currently evolving' },
    ],
  },
  {
    key: 'delivery',
    title: 'How will you deliver your product or service?',
    subtitle: 'Informs physical logistics safety vs digital system access policies.',
    options: [
      { value: 'physical', label: 'Physical location', desc: 'In-person store, warehouse, or on-site client delivery' },
      { value: 'online', label: 'Online / digital', desc: 'Cloud download, web portal, or digital service delivery' },
      { value: 'both', label: 'Both physical and online', desc: 'Omnichannel fulfillment across physical and digital' },
      { value: 'undecided', label: 'Not decided yet', desc: 'Delivery channels to be determined' },
    ],
  },
  {
    key: 'hiring',
    title: 'Do you expect to hire employees?',
    subtitle: 'Activates workplace health, employment contracts, and labor compliance.',
    options: [
      { value: 'solo', label: "I'll work alone initially", desc: 'Solo founder / owner-operator with no staff' },
      { value: 'small_team', label: 'Yes, a small team', desc: '1 to 5 employees, contractors, or support staff' },
      { value: 'growing_team', label: 'Yes, a growing team', desc: '6 or more full-time personnel across departments' },
      { value: 'unsure', label: 'Not sure yet', desc: 'Staffing needs depending on initial launch volume' },
    ],
  },
  {
    key: 'collects_data',
    title: 'Will you collect customer information?',
    subtitle: 'Triggers customer privacy, data retention, and confidentiality controls.',
    options: [
      { value: 'yes', label: 'Yes', desc: 'Customer names, phone numbers, delivery addresses, or emails' },
      { value: 'no', label: 'No', desc: 'Anonymous over-the-counter sales without records retention' },
      { value: 'unsure', label: 'Not sure yet', desc: 'May retain basic contact cards or marketing lists' },
    ],
  },
  {
    key: 'payments',
    title: 'How will you accept payments?',
    subtitle: 'Determines cash register balancing vs digital gateway reconciliation.',
    options: [
      { value: 'cash', label: 'Mainly cash', desc: 'Physical currency, daily drawer balancing, safe deposits' },
      { value: 'digital', label: 'Digital / online payments', desc: 'Cards, MFS (bKash/Nagad), bank transfers, gateways' },
      { value: 'both', label: 'Both', desc: 'Combination of physical cash and digital checkout' },
      { value: 'undecided', label: 'Not decided yet', desc: 'Payment rails to be configured' },
    ],
  },
  {
    key: 'first_help',
    title: 'What would you like help with first?',
    subtitle: 'Positions your highest-priority compliance topic at the top of your roadmap.',
    options: [
      { value: 'which_policies', label: 'Which company policies I should create', desc: 'Holistic overview of required corporate policies' },
      { value: 'registration_basics', label: 'Business registration and basic obligations', desc: 'Trade licenses, TIN, BIN, and founding registrations' },
      { value: 'employee_policies', label: 'Employee and workplace policies', desc: 'Employment letters, salary timelines, workplace rules' },
      { value: 'customer_data_policies', label: 'Customer and data protection policies', desc: 'Privacy standards, personal data security, consent' },
      { value: 'general_guide', label: 'A general starting guide', desc: 'Balanced operational foundations for new ventures' },
    ],
  },
];

const TIER_CONFIG: Record<PolicyTier, { label: string; badge: string; border: string }> = {
  start_now: {
    label: 'Start Now — Immediate Foundations',
    badge: 'bg-rose-50 text-rose-700 border-rose-200',
    border: 'border-slate-200 hover:border-slate-300',
  },
  soon: {
    label: 'Soon — Near-Term Operational Setup',
    badge: 'bg-amber-50 text-amber-800 border-amber-200',
    border: 'border-slate-200 hover:border-slate-300',
  },
  later: {
    label: 'Later — Growth & Scaling Governance',
    badge: 'bg-slate-100 text-slate-700 border-slate-200',
    border: 'border-slate-200 hover:border-slate-300',
  },
};

interface StartFreshWizardProps {
  onSOPCreated?: (doc: DocumentUploadResponse) => void;
}

export const StartFreshWizard: React.FC<StartFreshWizardProps> = ({ onSOPCreated }) => {
  const router = useRouter();

  // Lazy initial state: loads saved answers and progress from sessionStorage without useEffect
  const [answers, setAnswers] = useState<Partial<StarterAnswers>>(() => {
    if (typeof window === 'undefined') return {};
    return loadStarterAnswers();
  });

  const [currentStep, setCurrentStep] = useState<number>(() => {
    if (typeof window === 'undefined') return 0;
    return loadStarterStep();
  });

  const [guide, setGuide] = useState<StarterGuideResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Starter SOP form state
  const [companyName, setCompanyName] = useState('Apex Logistics Bangladesh Ltd.');
  const [sopLoading, setSopLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const currentQ = QUESTIONS[currentStep];
  const totalSteps = QUESTIONS.length;
  const currentAnswer = answers[currentQ.key];

  const handleSelectOption = (value: StarterAnswers[keyof StarterAnswers]) => {
    const updated = { ...answers, [currentQ.key]: value };
    setAnswers(updated);
    saveStarterAnswers(updated);
  };

  const handleNext = async () => {
    if (!currentAnswer) return;

    if (currentStep < totalSteps - 1) {
      const nextStep = currentStep + 1;
      setCurrentStep(nextStep);
      saveStarterStep(nextStep);
    } else {
      // Step 9 completed -> generate guide
      await handleSubmitGuide();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      const prevStep = currentStep - 1;
      setCurrentStep(prevStep);
      saveStarterStep(prevStep);
    }
  };

  const handleSubmitGuide = async () => {
    // Validate that all 9 answers are present
    const missing = QUESTIONS.find((q) => !answers[q.key]);
    if (missing) {
      setError(`Please answer "${missing.title}" before continuing.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await getStarterGuide(answers as StarterAnswers);
      setGuide(res);
      // Auto-expand the first policy card
      if (res.policies.length > 0) {
        setExpandedId(res.policies[0].id);
      }
    } catch (err: unknown) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to generate starter policy guide.');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateSOP = async () => {
    if (!answers.jurisdiction || answers.jurisdiction !== 'bangladesh') {
      return;
    }

    setSopLoading(true);
    setError(null);

    try {
      const doc = await createStarterSOP({
        ...(answers as StarterAnswers),
        company_name: companyName,
      });

      if (onSOPCreated) {
        onSOPCreated(doc);
      } else {
        saveWorkspace({
          companyProfileId: doc.company_profile_id,
          companyName,
          documentId: doc.document_id,
          documentName: doc.filename,
          sections: doc.sections,
        });

        // Navigate to regulations page as requested
        router.push('/regulations');
      }
    } catch (err: unknown) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to generate and index starter SOP.');
      setSopLoading(false);
    }
  };

  // -------------------------------------------------------------------------
  // Results Screen View
  // -------------------------------------------------------------------------
  if (guide) {
    const isBangladesh = answers.jurisdiction === 'bangladesh';
    const tiers: PolicyTier[] = ['start_now', 'soon', 'later'];

    return (
      <div className="space-y-8">
        
        {/* Results Header */}
        <div className="space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
            <span>Prioritized Starter Policy Roadmap</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Your Tailored Compliance Roadmap
          </h2>
          <p className="text-sm text-slate-600 leading-relaxed bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs">
            {guide.summary}
          </p>
        </div>

        {/* Jurisdiction Notice if applicable */}
        {guide.jurisdiction_notice && (
          <div className="p-4 rounded-2xl bg-amber-50/90 border border-amber-200 text-amber-950 text-xs flex items-start gap-3 shadow-2xs">
            <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold text-amber-900">Jurisdiction Assessment Notice</span>
              <p className="leading-relaxed font-medium">{guide.jurisdiction_notice}</p>
            </div>
          </div>
        )}

        {/* Grouped Policy Tiers */}
        <div className="space-y-6">
          {tiers.map((tier) => {
            const group = guide.policies.filter((p) => p.tier === tier);
            if (group.length === 0) return null;
            const config = TIER_CONFIG[tier];

            return (
              <div key={tier} className="space-y-3">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-slate-900">{config.label}</h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold border border-slate-200">
                    {group.length} {group.length === 1 ? 'Policy' : 'Policies'}
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {group.map((policy: StarterPolicyItem) => {
                    const isExpanded = expandedId === policy.id;

                    return (
                      <div
                        key={policy.id}
                        className={`bg-white border rounded-2xl p-5 transition-all shadow-2xs ${config.border}`}
                      >
                        <div
                          className="flex items-start justify-between gap-4 cursor-pointer select-none"
                          onClick={() => setExpandedId(isExpanded ? null : policy.id)}
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${config.badge}`}>
                                {tier.replace('_', ' ')}
                              </span>
                              <span className="text-xs text-slate-400 font-mono">#{policy.id}</span>
                            </div>
                            <h4 className="text-base font-bold text-slate-900 mt-1">{policy.title}</h4>
                            <p className="text-xs text-emerald-700 font-semibold">{policy.reason}</p>
                          </div>

                          <button
                            type="button"
                            aria-label={isExpanded ? 'Collapse policy details' : 'Expand policy details'}
                            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-50 shrink-0"
                          >
                            {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                          </button>
                        </div>

                        {/* Collapsible Content */}
                        {isExpanded && (
                          <div className="mt-4 pt-4 border-t border-slate-100 space-y-4 text-xs">
                            <div>
                              <span className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">What this policy covers:</span>
                              <p className="text-slate-600 mt-1 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-200/80">
                                {policy.covers}
                              </p>
                            </div>

                            <div>
                              <span className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">Recommended clauses & practices:</span>
                              <ul className="mt-2 space-y-2">
                                {policy.include_points.map((pt, idx) => (
                                  <li key={idx} className="flex items-start gap-2 text-slate-700 font-medium">
                                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                                    <span>{pt}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Legal Disclaimer */}
        <LegalDisclaimer />

        {/* Starter SOP Conversion Card */}
        <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xs">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-700">
              <FileText className="w-4 h-4" />
              <span>Step 2: Generate & Benchmark Draft SOP</span>
            </div>
            <h3 className="text-xl font-extrabold text-slate-900">
              Turn This Guide Into a Draft Company SOP
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              We can automatically compile your questionnaire answers into an initial draft SOP document, index it directly into ChromaDB vector storage, and benchmark it against the latest 2025 NBR VAT regulatory standard.
            </p>
          </div>

          {error && (
            <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
              {error}
            </div>
          )}

          {isBangladesh ? (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Company / Operating Name</label>
                <div className="relative max-w-md">
                  <Building2 className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:border-emerald-500 focus:bg-white"
                    placeholder="e.g. Apex Logistics Bangladesh Ltd."
                  />
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleGenerateSOP}
                  disabled={sopLoading}
                  className="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs shadow-sm flex items-center justify-center gap-2 transition-all"
                >
                  {sopLoading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Indexing Draft SOP into ChromaDB...</span>
                    </>
                  ) : (
                    <>
                      <span>Generate Starter SOP & Continue</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setGuide(null)}
                  className="w-full sm:w-auto px-5 py-3 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 font-semibold text-xs transition-all text-center"
                >
                  Edit My Answers
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <span>
                  Starter SOP generation and automated benchmarking currently requires <strong>Bangladesh</strong> jurisdiction because the engine actively audits against the NBR VAT SRO standard. You can download or review your policy roadmap above.
                </span>
              </div>

              <div>
                <button
                  type="button"
                  onClick={() => setGuide(null)}
                  className="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs shadow-sm"
                >
                  Edit My Answers
                </button>
              </div>
            </div>
          )}
        </div>

      </div>
    );
  }

  // -------------------------------------------------------------------------
  // 9-Question Wizard View
  // -------------------------------------------------------------------------
  const progressPercent = Math.round(((currentStep + 1) / totalSteps) * 100);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      
      {/* Progress Bar & Counter */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-semibold">
          <span className="text-emerald-700 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Question {currentStep + 1} of {totalSteps}</span>
          </span>
          <span className="text-slate-400 font-mono">{progressPercent}% Completed</span>
        </div>

        <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
          <div
            className="h-full bg-emerald-600 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
          {error}
        </div>
      )}

      {/* Question Card */}
      <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-8 space-y-6 shadow-2xs">
        
        <div className="space-y-1.5">
          <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
            {currentQ.title}
          </h2>
          <p className="text-xs text-slate-500 leading-relaxed">
            {currentQ.subtitle}
          </p>
        </div>

        {/* Large Keyboard-Accessible Radio Cards */}
        <div className="space-y-3" role="radiogroup" aria-label={currentQ.title}>
          {currentQ.options.map((opt) => {
            const isSelected = currentAnswer === opt.value;

            return (
              <div
                key={String(opt.value)}
                role="radio"
                tabIndex={0}
                aria-checked={isSelected}
                onClick={() => handleSelectOption(opt.value)}
                onKeyDown={(e) => {
                  if (e.key === ' ' || e.key === 'Enter') {
                    e.preventDefault();
                    handleSelectOption(opt.value);
                  }
                }}
                className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-center justify-between gap-4 select-none outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 ${
                  isSelected
                    ? 'bg-emerald-50/70 border-emerald-400 shadow-2xs ring-1 ring-emerald-400'
                    : 'bg-slate-50/50 border-slate-200 hover:bg-slate-50 hover:border-slate-300'
                }`}
              >
                <div className="space-y-0.5">
                  <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <span>{opt.label}</span>
                  </div>
                  {opt.desc && (
                    <p className="text-xs text-slate-500 leading-relaxed">{opt.desc}</p>
                  )}
                </div>

                <div
                  className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 transition-all ${
                    isSelected
                      ? 'border-emerald-600 bg-emerald-600 text-white'
                      : 'border-slate-300 bg-white'
                  }`}
                >
                  {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
                </div>
              </div>
            );
          })}
        </div>

        {/* Wizard Controls */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100 gap-3">
          <button
            type="button"
            onClick={handleBack}
            disabled={currentStep === 0 || loading}
            className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-30 disabled:pointer-events-none text-xs font-semibold flex items-center gap-1.5 transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back</span>
          </button>

          <button
            type="button"
            onClick={handleNext}
            disabled={!currentAnswer || loading}
            className="px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none text-white font-bold text-xs shadow-sm flex items-center gap-2 transition-all"
          >
            {loading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Generating Roadmap...</span>
              </>
            ) : currentStep === totalSteps - 1 ? (
              <>
                <span>Generate Starter Policy Guide</span>
                <Sparkles className="w-3.5 h-3.5" />
              </>
            ) : (
              <>
                <span>Next Question</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>

      </div>

    </div>
  );
};
