'use client';

/**
 * Timeline Zoom Slider Component
 *
 * Provides zoom control for horizontal and multi-track timeline views.
 * Includes slider, zoom in/out buttons, and current level indicator.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #2)
 */

import { useCallback } from 'react';
import { ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { getNextZoomLevel, getPreviousZoomLevel } from './timelineUtils';
import type { ZoomLevel } from '@/types/timeline';

/**
 * Zoom level labels for display
 */
const ZOOM_LABELS: Record<ZoomLevel, string> = {
  year: 'Year',
  quarter: 'Quarter',
  month: 'Month',
  week: 'Week',
  day: 'Day',
};

/**
 * Zoom levels in order (for slider)
 */
const ZOOM_LEVELS: ZoomLevel[] = ['year', 'quarter', 'month', 'week', 'day'];

interface TimelineZoomSliderProps {
  /** Current zoom level */
  zoomLevel: ZoomLevel;
  /** Callback when zoom level changes */
  onZoomChange: (level: ZoomLevel) => void;
  /** Optional className */
  className?: string;
  /** Whether to show label */
  showLabel?: boolean;
}

export function TimelineZoomSlider({
  zoomLevel,
  onZoomChange,
  className,
  showLabel = true,
}: TimelineZoomSliderProps) {
  const currentIndex = ZOOM_LEVELS.indexOf(zoomLevel);

  const handleZoomIn = useCallback(() => {
    const nextLevel = getNextZoomLevel(zoomLevel);
    if (nextLevel) {
      onZoomChange(nextLevel);
    }
  }, [zoomLevel, onZoomChange]);

  const handleZoomOut = useCallback(() => {
    const prevLevel = getPreviousZoomLevel(zoomLevel);
    if (prevLevel) {
      onZoomChange(prevLevel);
    }
  }, [zoomLevel, onZoomChange]);

  const handleSliderChange = useCallback(
    (values: number[]) => {
      const newIndex = values[0];
      if (newIndex !== undefined && newIndex >= 0 && newIndex < ZOOM_LEVELS.length) {
        const newLevel = ZOOM_LEVELS[newIndex];
        if (newLevel) {
          onZoomChange(newLevel);
        }
      }
    },
    [onZoomChange]
  );

  const canZoomIn = currentIndex < ZOOM_LEVELS.length - 1;
  const canZoomOut = currentIndex > 0;

  return (
    <div
      className={cn('flex items-center gap-2', className)}
      role="group"
      aria-label="Timeline zoom controls"
    >
      {/* Zoom out button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={handleZoomOut}
            disabled={!canZoomOut}
            aria-label="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Zoom out</TooltipContent>
      </Tooltip>

      {/* Slider */}
      <div className="w-24">
        <Slider
          value={[currentIndex]}
          onValueChange={handleSliderChange}
          min={0}
          max={ZOOM_LEVELS.length - 1}
          step={1}
          aria-label="Zoom level"
          aria-valuetext={ZOOM_LABELS[zoomLevel]}
        />
      </div>

      {/* Zoom in button */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={handleZoomIn}
            disabled={!canZoomIn}
            aria-label="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Zoom in</TooltipContent>
      </Tooltip>

      {/* Current level indicator */}
      {showLabel && (
        <span
          className="text-xs text-muted-foreground min-w-[60px] text-center"
          aria-live="polite"
        >
          {ZOOM_LABELS[zoomLevel]}
        </span>
      )}
    </div>
  );
}
