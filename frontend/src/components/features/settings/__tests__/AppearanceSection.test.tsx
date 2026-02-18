import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AppearanceSection } from '../AppearanceSection';

describe('AppearanceSection', () => {
  it('renders appearance section', () => {
    render(<AppearanceSection />);

    expect(screen.getByText('Appearance')).toBeInTheDocument();
    expect(screen.getByText('Theme')).toBeInTheDocument();
  });

  it('shows light mode indicator', () => {
    render(<AppearanceSection />);

    expect(screen.getByText('Light Mode')).toBeInTheDocument();
  });

  it('does not show dark or system theme options', () => {
    render(<AppearanceSection />);

    expect(screen.queryByText('Dark')).not.toBeInTheDocument();
    expect(screen.queryByText('System')).not.toBeInTheDocument();
  });

  it('shows description text', () => {
    render(<AppearanceSection />);

    expect(screen.getByText(/customize how jaanch looks/i)).toBeInTheDocument();
  });
});
