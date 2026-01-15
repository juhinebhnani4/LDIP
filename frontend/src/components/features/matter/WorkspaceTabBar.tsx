'use client';

import { useCallback, useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  FileText,
  Clock,
  Users,
  Quote,
  AlertTriangle,
  CheckCircle,
  FolderOpen,
  Loader2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { useWorkspaceStore } from '@/stores/workspaceStore';

/**
 * Tab IDs - must match route segments exactly
 */
export type TabId =
  | 'summary'
  | 'timeline'
  | 'entities'
  | 'citations'
  | 'contradictions'
  | 'verification'
  | 'documents';

/**
 * Tab configuration type
 */
interface TabConfig {
  id: TabId;
  label: string;
  icon: LucideIcon;
  epic: string;
}

/**
 * Tab configuration with labels, icons, and epic reference.
 * Order is critical - Summary → Timeline → Entities → Citations → Contradictions → Verification → Documents
 */
export const TAB_CONFIG: TabConfig[] = [
  { id: 'summary', label: 'Summary', icon: FileText, epic: 'Epic 10B' },
  { id: 'timeline', label: 'Timeline', icon: Clock, epic: 'Epic 10B' },
  { id: 'entities', label: 'Entities', icon: Users, epic: 'Epic 10C' },
  { id: 'citations', label: 'Citations', icon: Quote, epic: 'Epic 10C' },
  { id: 'contradictions', label: 'Contradictions', icon: AlertTriangle, epic: 'Phase 2' },
  { id: 'verification', label: 'Verification', icon: CheckCircle, epic: 'Epic 10D' },
  { id: 'documents', label: 'Documents', icon: FolderOpen, epic: 'Epic 10D' },
];

export const DEFAULT_TAB: TabId = 'summary';

export const TAB_LABELS = {
  summary: 'Summary',
  timeline: 'Timeline',
  entities: 'Entities',
  citations: 'Citations',
  contradictions: 'Contradictions',
  verification: 'Verification',
  documents: 'Documents',
} as const satisfies Record<TabId, string>;

export const TAB_EPIC_INFO = {
  summary: 'Epic 10B',
  timeline: 'Epic 10B',
  entities: 'Epic 10C',
  citations: 'Epic 10C',
  contradictions: 'Phase 2',
  verification: 'Epic 10D',
  documents: 'Epic 10D',
} as const satisfies Record<TabId, string>;

/**
 * Tab Status Indicator Component
 *
 * Displays either:
 * - Processing spinner when tab data is loading
 * - Issue count badge (destructive) when there are issues
 * - Regular count when items are ready
 */
interface TabStatusIndicatorProps {
  /** Tab label for accessible status announcements */
  tabLabel: string;
  count?: number;
  issueCount?: number;
  isProcessing?: boolean;
}

function TabStatusIndicator({
  tabLabel,
  count,
  issueCount,
  isProcessing,
}: TabStatusIndicatorProps) {
  // Processing state - show spinner
  if (isProcessing) {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        <span className="sr-only">{tabLabel} processing</span>
      </span>
    );
  }

  // Issue count - show destructive badge
  if (issueCount !== undefined && issueCount > 0) {
    return (
      <Badge variant="destructive" className="h-5 px-1.5 text-xs">
        {issueCount}
      </Badge>
    );
  }

  // Regular count - show muted text
  if (count !== undefined && count > 0) {
    return (
      <span className="text-xs text-muted-foreground">
        ({count})
      </span>
    );
  }

  return null;
}

/**
 * WorkspaceTabBar Component
 *
 * Horizontal tab navigation for the matter workspace.
 * Tabs: Summary → Timeline → Entities → Citations → Contradictions → Verification → Documents
 *
 * Layout from UX-Decisions-Log.md:
 * ┌─────────────────────────────────────────────────────────────────────────────────┐
 * │  TAB BAR                                                                        │
 * │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────┐│
 * │  │Summary  │ │Timeline │ │Entities │ │Citations│ │Contrad. │ │Verific. │ │Docs││
 * │  │         │ │  (12)   │ │  (18)   │ │ (3) ⚠   │ │  (7)    │ │  (5)    │ │(8) ││
 * │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────┘│
 * └─────────────────────────────────────────────────────────────────────────────────┘
 *
 * Story 10A.2: Tab Bar Navigation
 */
interface WorkspaceTabBarProps {
  /** Matter ID for the current workspace */
  matterId: string;
}

export function WorkspaceTabBar({ matterId }: WorkspaceTabBarProps) {
  const pathname = usePathname();
  const tabRefs = useRef<Map<TabId, HTMLAnchorElement>>(new Map());

  // Use Zustand selectors for tab state
  const tabCounts = useWorkspaceStore((state) => state.tabCounts);
  const tabProcessingStatus = useWorkspaceStore((state) => state.tabProcessingStatus);

  // Extract active tab from pathname
  const pathSegments = pathname.split('/');
  const lastSegment = pathSegments[pathSegments.length - 1];
  const isValidTab = TAB_CONFIG.some((tab) => tab.id === lastSegment);
  const activeTab: TabId = isValidTab ? (lastSegment as TabId) : DEFAULT_TAB;

  // Generate href for each tab
  const getTabHref = useCallback(
    (tabId: TabId) => `/matters/${matterId}/${tabId}`,
    [matterId]
  );

  // Keyboard navigation handler
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLAnchorElement>, currentIndex: number) => {
      let targetIndex: number | null = null;

      switch (event.key) {
        case 'ArrowLeft':
          targetIndex = currentIndex > 0 ? currentIndex - 1 : TAB_CONFIG.length - 1;
          break;
        case 'ArrowRight':
          targetIndex = currentIndex < TAB_CONFIG.length - 1 ? currentIndex + 1 : 0;
          break;
        case 'Home':
          targetIndex = 0;
          break;
        case 'End':
          targetIndex = TAB_CONFIG.length - 1;
          break;
        default:
          return;
      }

      if (targetIndex !== null && targetIndex >= 0 && targetIndex < TAB_CONFIG.length) {
        event.preventDefault();
        const targetTab = TAB_CONFIG[targetIndex] as TabConfig;
        const targetRef = tabRefs.current.get(targetTab.id);
        targetRef?.focus();
      }
    },
    []
  );

  // Set ref for each tab
  const setTabRef = useCallback((tabId: TabId, element: HTMLAnchorElement | null) => {
    if (element) {
      tabRefs.current.set(tabId, element);
    } else {
      tabRefs.current.delete(tabId);
    }
  }, []);

  return (
    <nav
      className="sticky top-14 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      role="tablist"
      aria-label="Matter workspace navigation"
    >
      <div className="container flex h-12 items-center overflow-x-auto px-4 sm:px-6">
        {TAB_CONFIG.map((tab, index) => {
          const isActive = activeTab === tab.id;
          const TabIcon = tab.icon;
          const stats = tabCounts[tab.id];
          const processingStatus = tabProcessingStatus[tab.id];
          const isProcessing = processingStatus === 'processing';

          return (
            <Link
              key={tab.id}
              id={`tab-${tab.id}`}
              ref={(el) => setTabRef(tab.id, el)}
              href={getTabHref(tab.id)}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.id}`}
              tabIndex={isActive ? 0 : -1}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-sm font-medium whitespace-nowrap',
                'border-b-2 -mb-[2px] transition-colors',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                isActive
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/50'
              )}
            >
              <TabIcon className="h-4 w-4" aria-hidden="true" />
              <span>{tab.label}</span>
              <TabStatusIndicator
                tabLabel={tab.label}
                count={stats?.count}
                issueCount={stats?.issueCount}
                isProcessing={isProcessing}
              />
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
