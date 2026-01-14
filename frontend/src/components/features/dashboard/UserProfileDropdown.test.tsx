import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { UserProfileDropdown } from './UserProfileDropdown';
import { createMockSupabaseClient } from '@/tests/mocks/supabase';

// Mock the Supabase client module
vi.mock('@/lib/supabase/client', () => ({
  createClient: vi.fn(),
}));

// Import after mocking
import { createClient } from '@/lib/supabase/client';
const mockedCreateClient = vi.mocked(createClient);

// Mock router
const mockPush = vi.fn();
const mockRefresh = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    refresh: mockRefresh,
  }),
}));

describe('UserProfileDropdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateClient.mockReturnValue(
      createMockSupabaseClient() as unknown as ReturnType<typeof createClient>
    );
  });

  it('renders user profile button', () => {
    render(<UserProfileDropdown initialUser={{ email: 'test@example.com', fullName: 'Test User' }} />);

    const button = screen.getByRole('button', { name: /user profile menu/i });
    expect(button).toBeInTheDocument();
  });

  it('displays user initials from full name', () => {
    render(<UserProfileDropdown initialUser={{ email: 'test@example.com', fullName: 'John Doe' }} />);

    expect(screen.getByText('JD')).toBeInTheDocument();
  });

  it('displays user initials from email when no full name', () => {
    render(<UserProfileDropdown initialUser={{ email: 'test@example.com', fullName: null }} />);

    expect(screen.getByText('TE')).toBeInTheDocument();
  });

  it('displays user name in the dropdown trigger', () => {
    render(<UserProfileDropdown initialUser={{ email: 'test@example.com', fullName: 'Test User' }} />);

    expect(screen.getByText('Test User')).toBeInTheDocument();
  });

  it('handles single name for initials', () => {
    render(<UserProfileDropdown initialUser={{ email: 'test@example.com', fullName: 'John' }} />);

    expect(screen.getByText('JO')).toBeInTheDocument();
  });

  it('fetches user from supabase client when no initial user provided', async () => {
    const mockClient = createMockSupabaseClient({
      user: {
        id: 'test-user-id',
        email: 'client@example.com',
        user_metadata: { full_name: 'Client User', avatar_url: null },
        created_at: '2024-01-01T00:00:00.000Z',
      },
    });
    mockedCreateClient.mockReturnValue(mockClient as unknown as ReturnType<typeof createClient>);

    render(<UserProfileDropdown />);

    await waitFor(() => {
      expect(mockClient.auth.getUser).toHaveBeenCalled();
    });
  });

  it('displays email username when no full name provided', () => {
    render(<UserProfileDropdown initialUser={{ email: 'john.doe@example.com', fullName: null }} />);

    expect(screen.getByText('john.doe')).toBeInTheDocument();
  });

  it('has correct button structure with avatar and chevron', () => {
    render(<UserProfileDropdown initialUser={{ email: 'test@example.com', fullName: 'Test User' }} />);

    const button = screen.getByRole('button', { name: /user profile menu/i });
    // Avatar initials present
    expect(screen.getByText('TU')).toBeInTheDocument();
    // User name visible
    expect(screen.getByText('Test User')).toBeInTheDocument();
    // Button contains SVG (chevron)
    const svg = button.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });
});
