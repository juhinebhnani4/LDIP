import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LiveDiscoveriesPanel } from './LiveDiscoveriesPanel';
import type {
  LiveDiscovery,
  DiscoveredEntity,
  DiscoveredDate,
  DiscoveredCitation,
  EarlyInsight,
} from '@/types/upload';

describe('LiveDiscoveriesPanel', () => {
  const createEntityDiscovery = (entities: DiscoveredEntity[]): LiveDiscovery => ({
    id: 'entity-1',
    type: 'entity',
    count: entities.length,
    details: entities,
    timestamp: new Date(),
  });

  const createDateDiscovery = (dateInfo: DiscoveredDate): LiveDiscovery => ({
    id: 'date-1',
    type: 'date',
    count: dateInfo.count,
    details: dateInfo,
    timestamp: new Date(),
  });

  const createCitationDiscovery = (citations: DiscoveredCitation[]): LiveDiscovery => ({
    id: 'citation-1',
    type: 'citation',
    count: citations.reduce((sum, c) => sum + c.count, 0),
    details: citations,
    timestamp: new Date(),
  });

  const createInsightDiscovery = (insight: EarlyInsight): LiveDiscovery => ({
    id: `insight-${Date.now()}`,
    type: 'insight',
    count: 1,
    details: insight,
    timestamp: new Date(),
  });

  describe('rendering', () => {
    it('renders header with live indicator', () => {
      render(<LiveDiscoveriesPanel discoveries={[]} />);

      expect(screen.getByText('LIVE DISCOVERIES')).toBeInTheDocument();
    });

    it('shows placeholder when no discoveries', () => {
      render(<LiveDiscoveriesPanel discoveries={[]} />);

      expect(
        screen.getByText(/analyzing documents.*discoveries will appear here/i)
      ).toBeInTheDocument();
    });

    it('has aria-live region for announcements', () => {
      render(<LiveDiscoveriesPanel discoveries={[]} />);

      const container = screen.getByText('LIVE DISCOVERIES').closest('div[aria-live]');
      expect(container).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('entities section', () => {
    it('displays entities with count', () => {
      const entities: DiscoveredEntity[] = [
        { name: 'Mehul Parekh', role: 'Petitioner' },
        { name: 'SEBI', role: 'Regulatory Authority' },
      ];
      const discovery = createEntityDiscovery(entities);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('ENTITIES FOUND (2)')).toBeInTheDocument();
    });

    it('shows entity names and roles', () => {
      const entities: DiscoveredEntity[] = [
        { name: 'Mehul Parekh', role: 'Petitioner' },
      ];
      const discovery = createEntityDiscovery(entities);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('Mehul Parekh')).toBeInTheDocument();
      expect(screen.getByText('(Petitioner)')).toBeInTheDocument();
    });

    it('shows only first 3 entities with "more" indicator', () => {
      const entities: DiscoveredEntity[] = [
        { name: 'Entity 1', role: 'Role 1' },
        { name: 'Entity 2', role: 'Role 2' },
        { name: 'Entity 3', role: 'Role 3' },
        { name: 'Entity 4', role: 'Role 4' },
        { name: 'Entity 5', role: 'Role 5' },
      ];
      const discovery = createEntityDiscovery(entities);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('Entity 1')).toBeInTheDocument();
      expect(screen.getByText('Entity 2')).toBeInTheDocument();
      expect(screen.getByText('Entity 3')).toBeInTheDocument();
      expect(screen.queryByText('Entity 4')).not.toBeInTheDocument();
      expect(screen.getByText('+2 more...')).toBeInTheDocument();
    });
  });

  describe('dates section', () => {
    it('displays date range', () => {
      const dateInfo: DiscoveredDate = {
        earliest: new Date('2016-05-12'),
        latest: new Date('2024-01-15'),
        count: 47,
      };
      const discovery = createDateDiscovery(dateInfo);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('DATES EXTRACTED (47)')).toBeInTheDocument();
      expect(screen.getByText('Earliest:')).toBeInTheDocument();
      expect(screen.getByText('Latest:')).toBeInTheDocument();
    });

    it('formats dates in readable format', () => {
      const dateInfo: DiscoveredDate = {
        earliest: new Date('2016-05-12'),
        latest: new Date('2024-01-15'),
        count: 47,
      };
      const discovery = createDateDiscovery(dateInfo);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('May 12, 2016')).toBeInTheDocument();
      expect(screen.getByText('Jan 15, 2024')).toBeInTheDocument();
    });
  });

  describe('citations section', () => {
    it('displays citations with total count', () => {
      const citations: DiscoveredCitation[] = [
        { actName: 'Securities Act 1992', count: 18 },
        { actName: 'SARFAESI Act 2002', count: 4 },
      ];
      const discovery = createCitationDiscovery(citations);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('CITATIONS DETECTED (22)')).toBeInTheDocument();
    });

    it('shows each act with its citation count', () => {
      const citations: DiscoveredCitation[] = [
        { actName: 'Securities Act 1992', count: 18 },
        { actName: 'SARFAESI Act 2002', count: 4 },
      ];
      const discovery = createCitationDiscovery(citations);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('Securities Act 1992')).toBeInTheDocument();
      expect(screen.getByText('(18)')).toBeInTheDocument();
      expect(screen.getByText('SARFAESI Act 2002')).toBeInTheDocument();
      expect(screen.getByText('(4)')).toBeInTheDocument();
    });
  });

  describe('timeline preview', () => {
    it('renders timeline preview when dates available', () => {
      const dateInfo: DiscoveredDate = {
        earliest: new Date('2016-05-12'),
        latest: new Date('2024-01-15'),
        count: 47,
      };
      const discovery = createDateDiscovery(dateInfo);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('TIMELINE PREVIEW')).toBeInTheDocument();
    });

    it('shows year labels on timeline', () => {
      const dateInfo: DiscoveredDate = {
        earliest: new Date('2016-01-01'),
        latest: new Date('2024-01-01'),
        count: 47,
      };
      const discovery = createDateDiscovery(dateInfo);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('2016')).toBeInTheDocument();
      expect(screen.getByText('2024')).toBeInTheDocument();
    });
  });

  describe('early insights section', () => {
    it('renders insights card when insights available', () => {
      const insight: EarlyInsight = {
        message: 'This case spans 7+ years',
        type: 'info',
        icon: 'lightbulb',
      };
      const discovery = createInsightDiscovery(insight);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      expect(screen.getByText('EARLY INSIGHTS')).toBeInTheDocument();
      expect(screen.getByText('This case spans 7+ years')).toBeInTheDocument();
    });

    it('renders info insights with lightbulb icon style', () => {
      const insight: EarlyInsight = {
        message: 'Info message',
        type: 'info',
        icon: 'lightbulb',
      };
      const discovery = createInsightDiscovery(insight);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      const insightElement = screen.getByText('Info message').parentElement;
      expect(insightElement).toHaveClass('bg-blue-50');
    });

    it('renders warning insights with alert style', () => {
      const insight: EarlyInsight = {
        message: 'Warning message',
        type: 'warning',
        icon: 'alert-triangle',
      };
      const discovery = createInsightDiscovery(insight);

      render(<LiveDiscoveriesPanel discoveries={[discovery]} />);

      const insightElement = screen.getByText('Warning message').parentElement;
      expect(insightElement).toHaveClass('bg-amber-50');
    });

    it('renders multiple insights', () => {
      const discoveries: LiveDiscovery[] = [
        createInsightDiscovery({
          message: 'First insight',
          type: 'info',
          icon: 'lightbulb',
        }),
        createInsightDiscovery({
          message: 'Second insight',
          type: 'warning',
          icon: 'alert-triangle',
        }),
      ];

      render(<LiveDiscoveriesPanel discoveries={discoveries} />);

      expect(screen.getByText('First insight')).toBeInTheDocument();
      expect(screen.getByText('Second insight')).toBeInTheDocument();
    });
  });

  describe('combined discoveries', () => {
    it('renders all discovery types together', () => {
      const discoveries: LiveDiscovery[] = [
        createEntityDiscovery([
          { name: 'Test Entity', role: 'Petitioner' },
        ]),
        createDateDiscovery({
          earliest: new Date('2020-01-01'),
          latest: new Date('2024-01-01'),
          count: 10,
        }),
        createCitationDiscovery([
          { actName: 'Test Act', count: 5 },
        ]),
        createInsightDiscovery({
          message: 'Test insight',
          type: 'info',
          icon: 'lightbulb',
        }),
      ];

      render(<LiveDiscoveriesPanel discoveries={discoveries} />);

      expect(screen.getByText('ENTITIES FOUND (1)')).toBeInTheDocument();
      expect(screen.getByText('DATES EXTRACTED (10)')).toBeInTheDocument();
      expect(screen.getByText('CITATIONS DETECTED (5)')).toBeInTheDocument();
      expect(screen.getByText('EARLY INSIGHTS')).toBeInTheDocument();
    });
  });

  describe('empty states', () => {
    it('does not show entities section when no entities', () => {
      const dateDiscovery = createDateDiscovery({
        earliest: new Date('2020-01-01'),
        latest: new Date('2024-01-01'),
        count: 10,
      });

      render(<LiveDiscoveriesPanel discoveries={[dateDiscovery]} />);

      expect(screen.queryByText(/ENTITIES FOUND/)).not.toBeInTheDocument();
    });

    it('does not show timeline preview when no dates', () => {
      const entityDiscovery = createEntityDiscovery([
        { name: 'Test', role: 'Role' },
      ]);

      render(<LiveDiscoveriesPanel discoveries={[entityDiscovery]} />);

      expect(screen.queryByText('TIMELINE PREVIEW')).not.toBeInTheDocument();
    });

    it('does not show insights card when no insights', () => {
      const entityDiscovery = createEntityDiscovery([
        { name: 'Test', role: 'Role' },
      ]);

      render(<LiveDiscoveriesPanel discoveries={[entityDiscovery]} />);

      expect(screen.queryByText('EARLY INSIGHTS')).not.toBeInTheDocument();
    });
  });
});
