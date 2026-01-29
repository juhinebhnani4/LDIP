import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorkspaceTabBar, TAB_CONFIG, DEFAULT_TAB, TAB_LABELS, PRIMARY_TABS, OVERFLOW_TABS } from './WorkspaceTabBar';

// Mock next/navigation
const mockPathname = vi.fn();
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
  }),
}));

// Mock the workspace store
const mockTabCounts = vi.fn();
const mockTabProcessingStatus = vi.fn();
vi.mock('@/stores/workspaceStore', () => ({
  useWorkspaceStore: (selector: (state: unknown) => unknown) => {
    const mockState = {
      tabCounts: mockTabCounts(),
      tabProcessingStatus: mockTabProcessingStatus(),
    };
    return selector(mockState);
  },
}));

describe('WorkspaceTabBar', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.mockReturnValue(`/matters/${mockMatterId}/summary`);
    mockTabCounts.mockReturnValue({});
    mockTabProcessingStatus.mockReturnValue({});
  });

  describe('Rendering (AC #1)', () => {
    it('renders primary tabs directly (Summary, Timeline, Documents)', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      // Primary tabs are visible as links with role="tab"
      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(3); // Summary, Timeline, Documents

      const expectedPrimaryTabs = ['Summary', 'Timeline', 'Documents'];
      tabs.forEach((tab, index) => {
        expect(tab).toHaveTextContent(expectedPrimaryTabs[index]!);
      });
    });

    it('renders More dropdown for overflow tabs', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      // More button should be visible
      const moreButton = screen.getByTestId('workspace-tab-more');
      expect(moreButton).toBeInTheDocument();
      expect(moreButton).toHaveTextContent('More');
    });

    it('displays primary tab labels', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      PRIMARY_TABS.forEach((tab) => {
        expect(screen.getByText(tab.label)).toBeInTheDocument();
      });
    });

    it('has correct ARIA roles', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      expect(screen.getByRole('tablist')).toBeInTheDocument();
      expect(screen.getByRole('tablist')).toHaveAttribute('aria-label', 'Matter workspace navigation');

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(3); // Primary tabs only
    });

    it('has sticky positioning below header', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const nav = screen.getByRole('tablist');
      expect(nav).toHaveClass('sticky');
      expect(nav).toHaveClass('top-16'); // Updated from top-14
      expect(nav).toHaveClass('z-40');
    });

    it('has container for tabs', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const nav = screen.getByRole('tablist');
      const container = nav.querySelector('.container');
      expect(container).toBeInTheDocument();
    });
  });

  describe('Navigation (AC #2)', () => {
    it('generates correct href for primary tabs', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      PRIMARY_TABS.forEach((tab) => {
        const tabElement = screen.getByRole('tab', { name: new RegExp(tab.label) });
        expect(tabElement).toHaveAttribute('href', `/matter/${mockMatterId}/${tab.id}`);
      });
    });

    it('highlights active primary tab based on URL', () => {
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/timeline`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      expect(timelineTab).toHaveAttribute('aria-selected', 'true');
      expect(timelineTab).toHaveClass('border-primary');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(summaryTab).toHaveAttribute('aria-selected', 'false');
      expect(summaryTab).toHaveClass('border-transparent');
    });

    it('shows active overflow tab label in More button', async () => {
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/entities`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      // When an overflow tab is active, the More button shows its label
      const moreButton = screen.getByTestId('workspace-tab-more');
      expect(moreButton).toHaveTextContent('Entities');
      expect(moreButton).toHaveClass('border-primary');
    });

    it('defaults to summary when path is invalid', () => {
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/invalid-tab`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(summaryTab).toHaveAttribute('aria-selected', 'true');
    });

    it('defaults to summary when at matter root', () => {
      mockPathname.mockReturnValue(`/matter/${mockMatterId}`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(summaryTab).toHaveAttribute('aria-selected', 'true');
    });

    it('sets tabIndex correctly for roving tabindex pattern on primary tabs', () => {
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/timeline`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const activeTab = screen.getByRole('tab', { name: /timeline/i });
      expect(activeTab).toHaveAttribute('tabIndex', '0');

      const inactiveTab = screen.getByRole('tab', { name: /summary/i });
      expect(inactiveTab).toHaveAttribute('tabIndex', '-1');
    });
  });

  describe('Badge Display (AC #3)', () => {
    it('displays badge with issue count on primary tabs when > 0', () => {
      mockTabCounts.mockReturnValue({
        documents: { count: 45, issueCount: 3 },
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      expect(within(documentsTab).getByText('3')).toBeInTheDocument();
    });

    it('hides badge when issue count is 0', () => {
      mockTabCounts.mockReturnValue({
        summary: { count: 1, issueCount: 0 },
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      // Should not have a badge element with "0"
      expect(within(summaryTab).queryByText('0')).not.toBeInTheDocument();
    });

    it('displays regular count when no issues on primary tabs', () => {
      mockTabCounts.mockReturnValue({
        timeline: { count: 24, issueCount: 0 },
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      expect(within(timelineTab).getByText('(24)')).toBeInTheDocument();
    });

    it('shows aggregate issue count on More button for overflow tabs', () => {
      mockTabCounts.mockReturnValue({
        entities: { count: 10, issueCount: 2 },
        citations: { count: 20, issueCount: 3 },
        contradictions: { count: 5, issueCount: 1 },
        verification: { count: 15, issueCount: 0 },
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      // More button should show total issue count from overflow tabs (2+3+1=6)
      const moreButton = screen.getByTestId('workspace-tab-more');
      expect(within(moreButton).getByText('6')).toBeInTheDocument();
    });
  });

  describe('Processing Status Indicators (AC #4)', () => {
    it('displays spinner for processing primary tabs', () => {
      mockTabProcessingStatus.mockReturnValue({
        timeline: 'processing',
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      const spinner = within(timelineTab).getByText('Timeline processing');
      expect(spinner).toHaveClass('sr-only');
      // The spinner icon should have animate-spin class
      expect(timelineTab.querySelector('.animate-spin')).toBeInTheDocument();
    });

    it('displays count for ready tabs', () => {
      mockTabCounts.mockReturnValue({
        documents: { count: 8, issueCount: 0 },
      });
      mockTabProcessingStatus.mockReturnValue({
        documents: 'ready',
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      expect(within(documentsTab).getByText('(8)')).toBeInTheDocument();
    });

    it('shows spinner instead of count when processing', () => {
      mockTabCounts.mockReturnValue({
        timeline: { count: 24, issueCount: 0 },
      });
      mockTabProcessingStatus.mockReturnValue({
        timeline: 'processing',
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      // Should show spinner, not count
      expect(timelineTab.querySelector('.animate-spin')).toBeInTheDocument();
      expect(within(timelineTab).queryByText('(24)')).not.toBeInTheDocument();
    });
  });

  describe('Keyboard Navigation', () => {
    it('supports arrow right navigation between primary tabs', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/summary`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      summaryTab.focus();

      await user.keyboard('{ArrowRight}');

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      expect(document.activeElement).toBe(timelineTab);
    });

    it('supports arrow left navigation between primary tabs', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/timeline`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      timelineTab.focus();

      await user.keyboard('{ArrowLeft}');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(document.activeElement).toBe(summaryTab);
    });

    it('wraps from last primary tab to first with arrow right', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/documents`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      documentsTab.focus();

      await user.keyboard('{ArrowRight}');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(document.activeElement).toBe(summaryTab);
    });

    it('wraps from first primary tab to last with arrow left', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/summary`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      summaryTab.focus();

      await user.keyboard('{ArrowLeft}');

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      expect(document.activeElement).toBe(documentsTab);
    });

    it('supports Home key to go to first primary tab', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/documents`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      documentsTab.focus();

      await user.keyboard('{Home}');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(document.activeElement).toBe(summaryTab);
    });

    it('supports End key to go to last primary tab', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/summary`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      summaryTab.focus();

      await user.keyboard('{End}');

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      expect(document.activeElement).toBe(documentsTab);
    });
  });

  describe('Accessibility', () => {
    it('has aria-selected on active primary tab', () => {
      mockPathname.mockReturnValue(`/matter/${mockMatterId}/timeline`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      expect(timelineTab).toHaveAttribute('aria-selected', 'true');

      const otherTabs = screen.getAllByRole('tab').filter((tab) => tab !== timelineTab);
      otherTabs.forEach((tab) => {
        expect(tab).toHaveAttribute('aria-selected', 'false');
      });
    });

    it('has aria-controls linking to tab panels for primary tabs', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      PRIMARY_TABS.forEach((tab) => {
        const tabElement = screen.getByRole('tab', { name: new RegExp(tab.label) });
        expect(tabElement).toHaveAttribute('aria-controls', `tabpanel-${tab.id}`);
      });
    });

    it('has id attribute for aria-labelledby reference from tab panels', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      PRIMARY_TABS.forEach((tab) => {
        const tabElement = screen.getByRole('tab', { name: new RegExp(tab.label) });
        expect(tabElement).toHaveAttribute('id', `tab-${tab.id}`);
      });
    });

    it('has visible focus indicator on primary tabs', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const tabs = screen.getAllByRole('tab');
      tabs.forEach((tab) => {
        expect(tab).toHaveClass('focus-visible:ring-2');
      });
    });

    it('icons are hidden from screen readers in primary tabs', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const tabs = screen.getAllByRole('tab');
      tabs.forEach((tab) => {
        const svg = tab.querySelector('svg');
        expect(svg).toHaveAttribute('aria-hidden', 'true');
      });
    });
  });

  describe('Default Tab', () => {
    it('DEFAULT_TAB constant is summary', () => {
      expect(DEFAULT_TAB).toBe('summary');
    });

    it('TAB_CONFIG has 7 items', () => {
      expect(TAB_CONFIG).toHaveLength(7);
    });

    it('TAB_LABELS has all tab entries', () => {
      expect(Object.keys(TAB_LABELS)).toHaveLength(7);
      TAB_CONFIG.forEach((tab) => {
        expect(TAB_LABELS[tab.id]).toBe(tab.label);
      });
    });
  });
});
