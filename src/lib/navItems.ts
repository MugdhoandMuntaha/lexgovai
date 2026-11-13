import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  FileText,
  Shield,
  Cpu,
  Bot,
  Radio,
  Newspaper,
  Bell,
  Users,
  KeyRound,
  LifeBuoy,
  CreditCard,
  User,
  Settings,
  BookOpen,
} from 'lucide-react';

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  primary: boolean;
  capability?: string;
  adminOnly?: boolean;
}

export const navItems: NavItem[] = [
  // 5 Primary items (visible in desktop header)
  {
    href: '/',
    label: 'Dashboard',
    icon: BarChart3,
    primary: true,
  },
  {
    href: '/upload',
    label: 'Upload SOP',
    icon: FileText,
    primary: true,
    capability: 'sop_upload',
  },
  {
    href: '/regulations',
    label: 'Regulations',
    icon: Shield,
    primary: true,
  },
  {
    href: '/analysis',
    label: 'Analysis',
    icon: Cpu,
    primary: true,
    capability: 'impact_analysis',
  },
  {
    href: '/assistant',
    label: 'Assistant',
    icon: Bot,
    primary: true,
    capability: 'ai_assistant',
  },

  // Secondary items (available in popup and mobile)
  {
    href: '/laws',
    label: 'Legal Library',
    icon: BookOpen,
    primary: false,
    capability: 'legal_library',
  },
  {
    href: '/monitoring',
    label: 'Monitoring',
    icon: Radio,
    primary: false,
    capability: 'automated_monitoring',
  },
  {
    href: '/news',
    label: 'News',
    icon: Newspaper,
    primary: false,
    capability: 'regulatory_news',
  },
  {
    href: '/notifications',
    label: 'Notifications',
    icon: Bell,
    primary: false,
  },
  {
    href: '/team',
    label: 'Team',
    icon: Users,
    primary: false,
    capability: 'team_collaboration',
  },
  {
    href: '/settings/api-keys',
    label: 'API Keys',
    icon: KeyRound,
    primary: false,
    capability: 'api_integrations',
  },
  {
    href: '/support',
    label: 'Support',
    icon: LifeBuoy,
    primary: false,
  },
  {
    href: '/pricing',
    label: 'Pricing',
    icon: CreditCard,
    primary: false,
  },
  {
    href: '/account',
    label: 'Account',
    icon: User,
    primary: false,
  },
  {
    href: '/admin',
    label: 'Admin',
    icon: Settings,
    primary: false,
    adminOnly: true,
  },
];

export const primaryNavItems = navItems.filter((item) => item.primary);

