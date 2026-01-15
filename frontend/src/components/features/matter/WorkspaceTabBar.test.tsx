import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorkspaceTabBar, TAB_CONFIG, DEFAULT_TAB, TAB_LABELS } from './WorkspaceTabBar';

// Mock next/navigation
const mockPathname = vi.fn();
vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
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
    it('renders all seven tabs in correct order', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(7);

      const expectedOrder = ['Summary', 'Timeline', 'Entities', 'Citations', 'Contradictions', 'Verification', 'Documents'];
      tabs.forEach((tab, index) => {
        expect(tab).toHaveTextContent(expectedOrder[index]!);
      });
    });

    it('displays tab labels', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      Object.values(TAB_LABELS).forEach((label) => {
        expect(screen.getByText(label)).toBeInTheDocument();
      });
    });

    it('has correct ARIA roles', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      expect(screen.getByRole('tablist')).toBeInTheDocument();
      expect(screen.getByRole('tablist')).toHaveAttribute('aria-label', 'Matter workspace navigation');

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(7);
    });

    it('has sticky positioning below header', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const nav = screen.getByRole('tablist');
      expect(nav).toHaveClass('sticky');
      expect(nav).toHaveClass('top-14');
      expect(nav).toHaveClass('z-40');
    });

    it('has horizontal scrollable container', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const nav = screen.getByRole('tablist');
      const container = nav.querySelector('.container');
      expect(container).toHaveClass('overflow-x-auto');
    });
  });

  describe('Navigation (AC #2)', () => {
    it('generates correct href for each tab', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      TAB_CONFIG.forEach((tab) => {
        const tabElement = screen.getByRole('tab', { name: new RegExp(tab.label) });
        expect(tabElement).toHaveAttribute('href', `/matters/${mockMatterId}/${tab.id}`);
      });
    });

    it('highlights active tab based on URL', () => {
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/timeline`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      expect(timelineTab).toHaveAttribute('aria-selected', 'true');
      expect(timelineTab).toHaveClass('border-primary');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(summaryTab).toHaveAttribute('aria-selected', 'false');
      expect(summaryTab).toHaveClass('border-transparent');
    });

    it('defaults to summary when path is invalid', () => {
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/invalid-tab`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(summaryTab).toHaveAttribute('aria-selected', 'true');
    });

    it('defaults to summary when at matter root', () => {
      mockPathname.mockReturnValue(`/matters/${mockMatterId}`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(summaryTab).toHaveAttribute('aria-selected', 'true');
    });

    it('sets tabIndex correctly for roving tabindex pattern', () => {
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/entities`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const activeTab = screen.getByRole('tab', { name: /entities/i });
      expect(activeTab).toHaveAttribute('tabIndex', '0');

      const inactiveTab = screen.getByRole('tab', { name: /summary/i });
      expect(inactiveTab).toHaveAttribute('tabIndex', '-1');
    });
  });

  describe('Badge Display (AC #3)', () => {
    it('displays badge with issue count when > 0', () => {
      mockTabCounts.mockReturnValue({
        citations: { count: 45, issueCount: 3 },
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const citationsTab = screen.getByRole('tab', { name: /citations/i });
      expect(within(citationsTab).getByText('3')).toBeInTheDocument();
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

    it('displays regular count when no issues', () => {
      mockTabCounts.mockReturnValue({
        timeline: { count: 24, issueCount: 0 },
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      expect(within(timelineTab).getByText('(24)')).toBeInTheDocument();
    });

    it('shows issue badge instead of count when both exist', () => {
      mockTabCounts.mockReturnValue({
        verification: { count: 12, issueCount: 5 },
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const verificationTab = screen.getByRole('tab', { name: /verification/i });
      // Should show issue count badge, not regular count
      expect(within(verificationTab).getByText('5')).toBeInTheDocument();
      expect(within(verificationTab).queryByText('(12)')).not.toBeInTheDocument();
    });
  });

  describe('Processing Status Indicators (AC #4)', () => {
    it('displays spinner for processing tabs', () => {
      mockTabProcessingStatus.mockReturnValue({
        entities: 'processing',
      });

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const entitiesTab = screen.getByRole('tab', { name: /entities/i });
      const spinner = within(entitiesTab).getByText('Entities processing');
      expect(spinner).toHaveClass('sr-only');
      // The spinner icon should have animate-spin class
      expect(entitiesTab.querySelector('.animate-spin')).toBeInTheDocument();
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
    it('supports arrow right navigation', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/summary`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      summaryTab.focus();

      await user.keyboard('{ArrowRight}');

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      expect(document.activeElement).toBe(timelineTab);
    });

    it('supports arrow left navigation', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/timeline`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const timelineTab = screen.getByRole('tab', { name: /timeline/i });
      timelineTab.focus();

      await user.keyboard('{ArrowLeft}');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(document.activeElement).toBe(summaryTab);
    });

    it('wraps from last to first with arrow right', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/documents`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      documentsTab.focus();

      await user.keyboard('{ArrowRight}');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(document.activeElement).toBe(summaryTab);
    });

    it('wraps from first to last with arrow left', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/summary`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      summaryTab.focus();

      await user.keyboard('{ArrowLeft}');

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      expect(document.activeElement).toBe(documentsTab);
    });

    it('supports Home key to go to first tab', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/verification`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const verificationTab = screen.getByRole('tab', { name: /verification/i });
      verificationTab.focus();

      await user.keyboard('{Home}');

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      expect(document.activeElement).toBe(summaryTab);
    });

    it('supports End key to go to last tab', async () => {
      const user = userEvent.setup();
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/summary`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const summaryTab = screen.getByRole('tab', { name: /summary/i });
      summaryTab.focus();

      await user.keyboard('{End}');

      const documentsTab = screen.getByRole('tab', { name: /documents/i });
      expect(document.activeElement).toBe(documentsTab);
    });
  });

  describe('Accessibility', () => {
    it('has aria-selected on active tab', () => {
      mockPathname.mockReturnValue(`/matters/${mockMatterId}/citations`);

      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const citationsTab = screen.getByRole('tab', { name: /citations/i });
      expect(citationsTab).toHaveAttribute('aria-selected', 'true');

      const otherTabs = screen.getAllByRole('tab').filter((tab) => tab !== citationsTab);
      otherTabs.forEach((tab) => {
        expect(tab).toHaveAttribute('aria-selected', 'false');
      });
    });

    it('has aria-controls linking to tab panels', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      TAB_CONFIG.forEach((tab) => {
        const tabElement = screen.getByRole('tab', { name: new RegExp(tab.label) });
        expect(tabElement).toHaveAttribute('aria-controls', `tabpanel-${tab.id}`);
      });
    });

    it('has id attribute for aria-labelledby reference from tab panels', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      TAB_CONFIG.forEach((tab) => {
        const tabElement = screen.getByRole('tab', { name: new RegExp(tab.label) });
        expect(tabElement).toHaveAttribute('id', `tab-${tab.id}`);
      });
    });

    it('has visible focus indicator', () => {
      render(<WorkspaceTabBar matterId={mockMatterId} />);

      const tabs = screen.getAllByRole('tab');
      tabs.forEach((tab) => {
        expect(tab).toHaveClass('focus-visible:ring-2');
      });
    });

    it('icons are hidden from screen readers', () => {
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
