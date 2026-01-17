import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AppearanceSection } from '../AppearanceSection';

// Mock useUserPreferences hook
const mockUpdatePreferences = vi.fn();

vi.mock('@/hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    preferences: {
      theme: 'system',
    },
    isLoading: false,
    updatePreferences: mockUpdatePreferences,
    isUpdating: false,
    updateError: null,
  }),
}));

describe('AppearanceSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdatePreferences.mockResolvedValue({ success: true });
  });

  it('renders appearance section', () => {
    render(<AppearanceSection />);

    expect(screen.getByText('Appearance')).toBeInTheDocument();
    expect(screen.getByText('Theme')).toBeInTheDocument();
  });

  it('displays all theme options', () => {
    render(<AppearanceSection />);

    expect(screen.getByText('Light')).toBeInTheDocument();
    expect(screen.getByText('Dark')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
  });

  it('shows current theme as selected', () => {
    render(<AppearanceSection />);

    // System option should have selected styling (checked via class)
    const systemButton = screen.getByRole('button', { name: /system/i });
    expect(systemButton).toHaveClass('border-primary');
  });

  it('calls updatePreferences when theme option is clicked', async () => {
    const user = userEvent.setup();
    render(<AppearanceSection />);

    const darkButton = screen.getByRole('button', { name: /dark/i });
    await user.click(darkButton);

    await waitFor(() => {
      expect(mockUpdatePreferences).toHaveBeenCalledWith({ theme: 'dark' });
    });
  });

  it('applies theme immediately on change', async () => {
    const user = userEvent.setup();
    render(<AppearanceSection />);

    const lightButton = screen.getByRole('button', { name: /light/i });
    await user.click(lightButton);

    await waitFor(() => {
      expect(mockUpdatePreferences).toHaveBeenCalledWith({ theme: 'light' });
    });
  });

  it('renders theme option buttons with labels', () => {
    render(<AppearanceSection />);

    const lightButton = screen.getByRole('button', { name: /light/i });
    const darkButton = screen.getByRole('button', { name: /dark/i });
    const systemButton = screen.getByRole('button', { name: /system/i });

    expect(lightButton).toBeInTheDocument();
    expect(darkButton).toBeInTheDocument();
    expect(systemButton).toBeInTheDocument();
  });

  it('shows description text', () => {
    render(<AppearanceSection />);

    expect(screen.getByText(/customize how ldip looks/i)).toBeInTheDocument();
  });
});
