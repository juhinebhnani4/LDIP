import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ViewToggle } from './ViewToggle';
import { useMatterStore } from '@/stores/matterStore';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('ViewToggle', () => {
  beforeEach(() => {
    useMatterStore.setState({
      viewMode: 'grid',
    });
    localStorageMock.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders grid and list toggle buttons', () => {
    render(<ViewToggle />);

    expect(screen.getByRole('radio', { name: /grid view/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /list view/i })).toBeInTheDocument();
  });

  it('has grid button pressed when viewMode is grid', () => {
    useMatterStore.setState({ viewMode: 'grid' });

    render(<ViewToggle />);

    const gridButton = screen.getByRole('radio', { name: /grid view/i });
    expect(gridButton).toHaveAttribute('data-state', 'on');

    const listButton = screen.getByRole('radio', { name: /list view/i });
    expect(listButton).toHaveAttribute('data-state', 'off');
  });

  it('has list button pressed when viewMode is list', () => {
    useMatterStore.setState({ viewMode: 'list' });

    render(<ViewToggle />);

    const listButton = screen.getByRole('radio', { name: /list view/i });
    expect(listButton).toHaveAttribute('data-state', 'on');

    const gridButton = screen.getByRole('radio', { name: /grid view/i });
    expect(gridButton).toHaveAttribute('data-state', 'off');
  });

  it('switches to list view when list button clicked', () => {
    useMatterStore.setState({ viewMode: 'grid' });

    render(<ViewToggle />);

    const listButton = screen.getByRole('radio', { name: /list view/i });
    fireEvent.click(listButton);

    expect(useMatterStore.getState().viewMode).toBe('list');
  });

  it('switches to grid view when grid button clicked', () => {
    useMatterStore.setState({ viewMode: 'list' });

    render(<ViewToggle />);

    const gridButton = screen.getByRole('radio', { name: /grid view/i });
    fireEvent.click(gridButton);

    expect(useMatterStore.getState().viewMode).toBe('grid');
  });

  it('persists view preference to localStorage', () => {
    render(<ViewToggle />);

    const listButton = screen.getByRole('radio', { name: /list view/i });
    fireEvent.click(listButton);

    expect(localStorageMock.getItem('dashboard_view_preference')).toBe('list');
  });

  it('has proper aria-label on toggle group', () => {
    render(<ViewToggle />);

    expect(screen.getByRole('group', { name: /view mode/i })).toBeInTheDocument();
  });

  it('has title attributes for tooltips', () => {
    render(<ViewToggle />);

    expect(screen.getByRole('radio', { name: /grid view/i })).toHaveAttribute('title', 'Grid view');
    expect(screen.getByRole('radio', { name: /list view/i })).toHaveAttribute('title', 'List view');
  });

  it('applies custom className when provided', () => {
    const { container } = render(<ViewToggle className="custom-class" />);

    const toggleGroup = container.querySelector('[data-slot="toggle-group"]');
    expect(toggleGroup).toHaveClass('custom-class');
  });
});
