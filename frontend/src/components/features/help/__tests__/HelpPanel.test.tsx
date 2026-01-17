import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HelpPanel } from '../HelpPanel';

describe('HelpPanel', () => {
  it('does not render when closed', () => {
    render(<HelpPanel open={false} onOpenChange={vi.fn()} />);

    expect(screen.queryByText('Help Center')).not.toBeInTheDocument();
  });

  it('renders when open', () => {
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByText('Help Center')).toBeInTheDocument();
  });

  it('renders search input', () => {
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByPlaceholderText('Search help topics...')).toBeInTheDocument();
  });

  it('renders all categories', () => {
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByText('Getting Started')).toBeInTheDocument();
    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
    expect(screen.getByText('Chat & Q&A')).toBeInTheDocument();
  });

  it('navigates to category when clicked', async () => {
    const user = userEvent.setup();
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    await user.click(screen.getByText('Getting Started'));

    // Should show category header
    expect(screen.getByRole('heading', { name: 'Getting Started' })).toBeInTheDocument();
  });

  it('shows search results when typing', async () => {
    const user = userEvent.setup();
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    const searchInput = screen.getByPlaceholderText('Search help topics...');
    await user.type(searchInput, 'upload');

    // Should show search results - "Uploading Documents" entry should appear
    expect(screen.getByText('Uploading Documents')).toBeInTheDocument();
  });

  it('shows no results message for non-matching search', async () => {
    const user = userEvent.setup();
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    const searchInput = screen.getByPlaceholderText('Search help topics...');
    await user.type(searchInput, 'xyznonexistent');

    expect(screen.getByText(/no results found/i)).toBeInTheDocument();
  });

  it('clears search when clear button clicked', async () => {
    const user = userEvent.setup();
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    const searchInput = screen.getByPlaceholderText('Search help topics...');
    await user.type(searchInput, 'upload');

    // Click clear button
    const clearButton = screen.getByRole('button', { name: /clear search/i });
    await user.click(clearButton);

    expect(searchInput).toHaveValue('');
  });

  it('shows back button when in a category', async () => {
    const user = userEvent.setup();
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    await user.click(screen.getByText('Getting Started'));

    const backButton = screen.getByRole('button', { name: /back/i });
    expect(backButton).toBeInTheDocument();
  });

  it('navigates back when back button clicked', async () => {
    const user = userEvent.setup();
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    // Navigate to category
    await user.click(screen.getByText('Getting Started'));
    expect(screen.getByRole('heading', { name: 'Getting Started' })).toBeInTheDocument();

    // Click back
    const backButton = screen.getByRole('button', { name: /back/i });
    await user.click(backButton);

    // Should be back at main view
    expect(screen.getByRole('heading', { name: 'Help Center' })).toBeInTheDocument();
  });

  it('shows entry content when entry clicked', async () => {
    const user = userEvent.setup();
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    // Navigate to Getting Started category
    await user.click(screen.getByText('Getting Started'));

    // Click on an entry
    await user.click(screen.getByText('Welcome to jaanch.ai'));

    // Should show entry content - the title becomes the SheetTitle heading
    expect(screen.getByText(/key features/i)).toBeInTheDocument();
  });

  it('renders contact support link', () => {
    render(<HelpPanel open={true} onOpenChange={vi.fn()} />);

    expect(screen.getByText('Contact support')).toBeInTheDocument();
  });
});
