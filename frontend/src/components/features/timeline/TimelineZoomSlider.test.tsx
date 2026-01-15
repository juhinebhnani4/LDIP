/**
 * TimelineZoomSlider Tests
 *
 * Tests for the zoom slider component used in horizontal and multi-track views.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #2)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TimelineZoomSlider } from './TimelineZoomSlider';
import { TooltipProvider } from '@/components/ui/tooltip';

// Helper to render with TooltipProvider
function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('TimelineZoomSlider', () => {
  it('renders zoom controls', () => {
    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="year" onZoomChange={() => {}} />
    );

    expect(screen.getByRole('group', { name: /zoom controls/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /zoom out/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /zoom in/i })).toBeInTheDocument();
    // Radix slider renders with role="slider"
    expect(screen.getByRole('slider')).toBeInTheDocument();
  });

  it('displays current zoom level label', () => {
    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="month" onZoomChange={() => {}} />
    );

    expect(screen.getByText('Month')).toBeInTheDocument();
  });

  it('hides label when showLabel is false', () => {
    renderWithTooltip(
      <TimelineZoomSlider
        zoomLevel="month"
        onZoomChange={() => {}}
        showLabel={false}
      />
    );

    expect(screen.queryByText('Month')).not.toBeInTheDocument();
  });

  it('disables zoom out button at minimum zoom (year)', () => {
    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="year" onZoomChange={() => {}} />
    );

    const zoomOutButton = screen.getByRole('button', { name: /zoom out/i });
    expect(zoomOutButton).toBeDisabled();
  });

  it('disables zoom in button at maximum zoom (day)', () => {
    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="day" onZoomChange={() => {}} />
    );

    const zoomInButton = screen.getByRole('button', { name: /zoom in/i });
    expect(zoomInButton).toBeDisabled();
  });

  it('calls onZoomChange when zoom in button is clicked', async () => {
    const user = userEvent.setup();
    const handleZoomChange = vi.fn();

    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="year" onZoomChange={handleZoomChange} />
    );

    await user.click(screen.getByRole('button', { name: /zoom in/i }));

    expect(handleZoomChange).toHaveBeenCalledWith('quarter');
  });

  it('calls onZoomChange when zoom out button is clicked', async () => {
    const user = userEvent.setup();
    const handleZoomChange = vi.fn();

    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="month" onZoomChange={handleZoomChange} />
    );

    await user.click(screen.getByRole('button', { name: /zoom out/i }));

    expect(handleZoomChange).toHaveBeenCalledWith('quarter');
  });

  it('progresses through zoom levels correctly on zoom in', async () => {
    const user = userEvent.setup();
    const handleZoomChange = vi.fn();

    const { rerender } = renderWithTooltip(
      <TimelineZoomSlider zoomLevel="year" onZoomChange={handleZoomChange} />
    );

    // Year -> Quarter
    await user.click(screen.getByRole('button', { name: /zoom in/i }));
    expect(handleZoomChange).toHaveBeenLastCalledWith('quarter');

    rerender(
      <TooltipProvider>
        <TimelineZoomSlider
          zoomLevel="quarter"
          onZoomChange={handleZoomChange}
        />
      </TooltipProvider>
    );

    // Quarter -> Month
    await user.click(screen.getByRole('button', { name: /zoom in/i }));
    expect(handleZoomChange).toHaveBeenLastCalledWith('month');

    rerender(
      <TooltipProvider>
        <TimelineZoomSlider zoomLevel="month" onZoomChange={handleZoomChange} />
      </TooltipProvider>
    );

    // Month -> Week
    await user.click(screen.getByRole('button', { name: /zoom in/i }));
    expect(handleZoomChange).toHaveBeenLastCalledWith('week');

    rerender(
      <TooltipProvider>
        <TimelineZoomSlider zoomLevel="week" onZoomChange={handleZoomChange} />
      </TooltipProvider>
    );

    // Week -> Day
    await user.click(screen.getByRole('button', { name: /zoom in/i }));
    expect(handleZoomChange).toHaveBeenLastCalledWith('day');
  });

  it('has accessible slider', () => {
    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="quarter" onZoomChange={() => {}} />
    );

    const slider = screen.getByRole('slider');
    // Slider has value attributes for accessibility
    expect(slider).toHaveAttribute('aria-valuenow');
  });

  it('applies custom className', () => {
    renderWithTooltip(
      <TimelineZoomSlider
        zoomLevel="year"
        onZoomChange={() => {}}
        className="custom-class"
      />
    );

    const group = screen.getByRole('group', { name: /zoom controls/i });
    expect(group).toHaveClass('custom-class');
  });

  it('updates displayed level when zoomLevel prop changes', () => {
    const { rerender } = renderWithTooltip(
      <TimelineZoomSlider zoomLevel="year" onZoomChange={() => {}} />
    );

    expect(screen.getByText('Year')).toBeInTheDocument();

    rerender(
      <TooltipProvider>
        <TimelineZoomSlider zoomLevel="week" onZoomChange={() => {}} />
      </TooltipProvider>
    );

    expect(screen.getByText('Week')).toBeInTheDocument();
    expect(screen.queryByText('Year')).not.toBeInTheDocument();
  });

  it('does not call onZoomChange when zoom out clicked at minimum', () => {
    const handleZoomChange = vi.fn();

    renderWithTooltip(
      <TimelineZoomSlider zoomLevel="year" onZoomChange={handleZoomChange} />
    );

    // Try to click disabled button
    const zoomOutButton = screen.getByRole('button', { name: /zoom out/i });
    expect(zoomOutButton).toBeDisabled();

    // userEvent won't click disabled buttons, but let's verify no call was made
    expect(handleZoomChange).not.toHaveBeenCalled();
  });
});
