'use client';

import { useCallback, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  FileText,
  Clock,
  Users,
  Quote,
  AlertTriangle,
  CheckCircle,
  FolderOpen,
  Loader2,
  MoreHorizontal,
  ChevronDown,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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

/**
 * Primary tabs shown directly in the tab bar.
 * These are the most frequently accessed tabs.
 */
export const PRIMARY_TAB_IDS: TabId[] = ['summary', 'timeline', 'documents'];

/**
 * Overflow tabs shown in the "More" dropdown.
 * These are analytical/secondary features.
 */
export const OVERFLOW_TAB_IDS: TabId[] = ['entities', 'citations', 'contradictions', 'verification'];

/** Get tab config arrays split by primary/overflow */
export const PRIMARY_TABS = TAB_CONFIG.filter((t) => PRIMARY_TAB_IDS.includes(t.id));
export const OVERFLOW_TABS = TAB_CONFIG.filter((t) => OVERFLOW_TAB_IDS.includes(t.id));

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
 * Primary tabs shown directly: Summary, Timeline, Documents
 * Overflow tabs in "More" dropdown: Entities, Citations, Contradictions, Verification
 *
 * Layout (UX density optimization):
 * ┌──────────────────────────────────────────────────────────────┐
 * │  TAB BAR                                                     │
 * │  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────────┐ │
 * │  │Summary  │ │ Timeline │ │ Documents │ │ More ▾ (⚠ 3)    │ │
 * │  │         │ │   (12)   │ │    (8)    │ │                 │ │
 * │  └─────────┘ └──────────┘ └───────────┘ └─────────────────┘ │
 * └──────────────────────────────────────────────────────────────┘
 *
 * When an overflow tab is active, "More" shows the active tab's icon + label.
 *
 * Story 10A.2: Tab Bar Navigation
 */
interface WorkspaceTabBarProps {
  /** Matter ID for the current workspace */
  matterId: string;
}

export function WorkspaceTabBar({ matterId }: WorkspaceTabBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const tabRefs = useRef<Map<TabId, HTMLAnchorElement>>(new Map());
  const [moreOpen, setMoreOpen] = useState(false);

  // Use Zustand selectors for tab state
  const tabCounts = useWorkspaceStore((state) => state.tabCounts);
  const tabProcessingStatus = useWorkspaceStore((state) => state.tabProcessingStatus);

  // Extract active tab from pathname
  const pathSegments = pathname.split('/');
  const lastSegment = pathSegments[pathSegments.length - 1];
  const isValidTab = TAB_CONFIG.some((tab) => tab.id === lastSegment);
  const activeTab: TabId = isValidTab ? (lastSegment as TabId) : DEFAULT_TAB;

  // Check if active tab is in overflow menu
  const isOverflowTabActive = OVERFLOW_TAB_IDS.includes(activeTab);
  const activeOverflowTab = isOverflowTabActive
    ? OVERFLOW_TABS.find((t) => t.id === activeTab)
    : null;

  // Generate href for each tab
  const getTabHref = useCallback(
    (tabId: TabId) => `/matter/${matterId}/${tabId}`,
    [matterId]
  );

  // Keyboard navigation handler (only for primary tabs now)
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLAnchorElement>, currentIndex: number) => {
      let targetIndex: number | null = null;

      switch (event.key) {
        case 'ArrowLeft':
          targetIndex = currentIndex > 0 ? currentIndex - 1 : PRIMARY_TABS.length - 1;
          break;
        case 'ArrowRight':
          targetIndex = currentIndex < PRIMARY_TABS.length - 1 ? currentIndex + 1 : 0;
          break;
        case 'Home':
          targetIndex = 0;
          break;
        case 'End':
          targetIndex = PRIMARY_TABS.length - 1;
          break;
        default:
          return;
      }

      if (targetIndex !== null && targetIndex >= 0 && targetIndex < PRIMARY_TABS.length) {
        event.preventDefault();
        const targetTab = PRIMARY_TABS[targetIndex] as TabConfig;
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

  // Calculate total issues in overflow tabs for badge
  const overflowIssueCount = OVERFLOW_TABS.reduce((sum, tab) => {
    const stats = tabCounts[tab.id];
    return sum + (stats?.issueCount ?? 0);
  }, 0);

  return (
    <nav
      className="sticky top-16 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      role="tablist"
      aria-label="Matter workspace navigation"
      data-testid="workspace-tab-bar"
    >
      <div className="container flex h-14 items-center px-4 sm:px-6">
        {/* Primary tabs */}
        {PRIMARY_TABS.map((tab, index) => {
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
              data-testid={`workspace-tab-${tab.id}`}
              className={cn(
                'flex items-center gap-2.5 px-5 py-3 text-sm font-medium whitespace-nowrap',
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

        {/* More dropdown for overflow tabs */}
        <DropdownMenu open={moreOpen} onOpenChange={setMoreOpen}>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              data-testid="workspace-tab-more"
              className={cn(
                'flex items-center gap-1.5 px-4 py-2 text-sm font-medium whitespace-nowrap h-auto',
                'border-b-2 -mb-[2px] rounded-none transition-colors',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                isOverflowTabActive
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/50'
              )}
            >
              {activeOverflowTab ? (
                <>
                  <activeOverflowTab.icon className="h-4 w-4" aria-hidden="true" />
                  <span>{activeOverflowTab.label}</span>
                </>
              ) : (
                <>
                  <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                  <span>More</span>
                </>
              )}
              <ChevronDown className="h-3 w-3 ml-0.5" aria-hidden="true" />
              {overflowIssueCount > 0 && !isOverflowTabActive && (
                <Badge variant="destructive" className="h-5 px-1.5 text-xs ml-1">
                  {overflowIssueCount}
                </Badge>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            {OVERFLOW_TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              const TabIcon = tab.icon;
              const stats = tabCounts[tab.id];
              const processingStatus = tabProcessingStatus[tab.id];
              const isProcessing = processingStatus === 'processing';

              return (
                <DropdownMenuItem
                  key={tab.id}
                  data-testid={`workspace-tab-${tab.id}`}
                  className={cn(
                    'flex items-center gap-2 cursor-pointer',
                    isActive && 'bg-accent'
                  )}
                  onClick={() => {
                    router.push(getTabHref(tab.id));
                    setMoreOpen(false);
                  }}
                >
                  <TabIcon className="h-4 w-4" aria-hidden="true" />
                  <span className="flex-1">{tab.label}</span>
                  <TabStatusIndicator
                    tabLabel={tab.label}
                    count={stats?.count}
                    issueCount={stats?.issueCount}
                    isProcessing={isProcessing}
                  />
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  );
}
