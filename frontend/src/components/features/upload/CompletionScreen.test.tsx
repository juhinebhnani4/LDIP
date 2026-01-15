import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CompletionScreen } from './CompletionScreen';
import { useUploadWizardStore } from '@/stores/uploadWizardStore';
import type { LiveDiscovery } from '@/types/upload';

// Mock Next.js navigation
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
  }),
}));

// Helper to create mock file
function createMockFile(name: string, size: number = 1024): File {
  const file = new File(['test'], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

describe('CompletionScreen', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // Reset store before each test
    useUploadWizardStore.getState().reset();
    mockPush.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('renders status role container', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('displays "Processing Complete!" message', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      expect(screen.getByText('Processing Complete!')).toBeInTheDocument();
    });

    it('displays matter name in ready message', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'SEBI v. Parekh Securities',
      });

      render(<CompletionScreen />);

      expect(screen.getByText(/SEBI v. Parekh Securities/)).toBeInTheDocument();
      expect(screen.getByText(/is ready to explore/)).toBeInTheDocument();
    });

    it('shows default name when matter name is empty', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: '',
      });

      render(<CompletionScreen />);

      expect(screen.getByText(/New Matter/)).toBeInTheDocument();
    });

    it('displays document count in summary', () => {
      useUploadWizardStore.setState({
        files: [
          createMockFile('file1.pdf'),
          createMockFile('file2.pdf'),
          createMockFile('file3.pdf'),
        ],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      expect(screen.getByText('3 documents')).toBeInTheDocument();
    });

    it('displays entity count from discoveries', () => {
      const discoveries: LiveDiscovery[] = [
        {
          id: '1',
          type: 'entity',
          count: 34,
          details: [{ name: 'Test Entity', role: 'Petitioner' }],
          timestamp: new Date(),
        },
      ];

      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
        liveDiscoveries: discoveries,
      });

      render(<CompletionScreen />);

      expect(screen.getByText('34 entities discovered')).toBeInTheDocument();
    });

    it('displays date count from discoveries', () => {
      const discoveries: LiveDiscovery[] = [
        {
          id: '1',
          type: 'date',
          count: 47,
          details: { earliest: new Date(), latest: new Date(), count: 47 },
          timestamp: new Date(),
        },
      ];

      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
        liveDiscoveries: discoveries,
      });

      render(<CompletionScreen />);

      expect(screen.getByText('47 timeline events')).toBeInTheDocument();
    });

    it('displays citation count from discoveries', () => {
      const discoveries: LiveDiscovery[] = [
        {
          id: '1',
          type: 'citation',
          count: 23,
          details: [{ actName: 'SARFAESI Act', count: 23 }],
          timestamp: new Date(),
        },
      ];

      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
        liveDiscoveries: discoveries,
      });

      render(<CompletionScreen />);

      expect(screen.getByText('23 citations detected')).toBeInTheDocument();
    });

    it('renders Go to Workspace Now button', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      expect(
        screen.getByRole('button', { name: /go to workspace now/i })
      ).toBeInTheDocument();
    });
  });

  describe('countdown', () => {
    it('shows initial countdown of 3 seconds', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      expect(screen.getByText(/redirecting in 3 seconds/i)).toBeInTheDocument();
    });

    it('auto-redirects after countdown completes', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      // Run all timers
      act(() => {
        vi.runAllTimers();
      });

      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('navigation', () => {
    it('redirects to dashboard on button click', async () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      const button = screen.getByRole('button', { name: /go to workspace now/i });

      await act(async () => {
        await userEvent.click(button);
      });

      expect(mockPush).toHaveBeenCalledWith('/');
    });

    it('calls onRedirect callback when provided', async () => {
      const onRedirect = vi.fn();

      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen onRedirect={onRedirect} />);

      const button = screen.getByRole('button', { name: /go to workspace now/i });

      await act(async () => {
        await userEvent.click(button);
      });

      expect(onRedirect).toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has status role for screen reader announcements', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('countdown has aria-live for updates', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      const countdown = screen.getByText(/redirecting in/i);
      expect(countdown).toHaveAttribute('aria-live', 'polite');
    });

    it('Go to Workspace button is keyboard accessible', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
      });

      render(<CompletionScreen />);

      const button = screen.getByRole('button', { name: /go to workspace now/i });
      expect(button).not.toBeDisabled();
    });
  });

  describe('summary stats', () => {
    it('shows 0 for missing discovery types', () => {
      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
        liveDiscoveries: [],
      });

      render(<CompletionScreen />);

      expect(screen.getByText('0 entities discovered')).toBeInTheDocument();
      expect(screen.getByText('0 timeline events')).toBeInTheDocument();
      expect(screen.getByText('0 citations detected')).toBeInTheDocument();
    });

    it('handles multiple discoveries of same type', () => {
      const discoveries: LiveDiscovery[] = [
        {
          id: '1',
          type: 'entity',
          count: 10,
          details: [{ name: 'Entity 1', role: 'Petitioner' }],
          timestamp: new Date(),
        },
        {
          id: '2',
          type: 'entity',
          count: 20, // This should not appear since we only take first match
          details: [{ name: 'Entity 2', role: 'Respondent' }],
          timestamp: new Date(),
        },
      ];

      useUploadWizardStore.setState({
        files: [createMockFile('test.pdf')],
        matterName: 'Test Matter',
        liveDiscoveries: discoveries,
      });

      render(<CompletionScreen />);

      // First discovery of type is used
      expect(screen.getByText('10 entities discovered')).toBeInTheDocument();
    });
  });
});
