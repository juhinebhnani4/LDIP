'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { GripHorizontal, Minimize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  useQAPanelStore,
  MIN_FLOAT_WIDTH,
  MIN_FLOAT_HEIGHT,
} from '@/stores/qaPanelStore';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';

/**
 * Floating Q&A Panel
 *
 * Draggable, resizable floating panel for the Q&A assistant.
 * Can be moved anywhere within the viewport and resized from the corner.
 *
 * Features:
 * - Drag-to-move via header
 * - Corner resize handle
 * - Constrained to viewport
 * - Position and size persisted to localStorage
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 */
interface FloatingQAPanelProps {
  /** Matter ID for the current workspace */
  matterId: string;
}

export function FloatingQAPanel({ matterId: _matterId }: FloatingQAPanelProps) {
  const floatX = useQAPanelStore((state) => state.floatX);
  const floatY = useQAPanelStore((state) => state.floatY);
  const floatWidth = useQAPanelStore((state) => state.floatWidth);
  const floatHeight = useQAPanelStore((state) => state.floatHeight);
  const setFloatPosition = useQAPanelStore((state) => state.setFloatPosition);
  const setFloatSize = useQAPanelStore((state) => state.setFloatSize);
  const setPosition = useQAPanelStore((state) => state.setPosition);

  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragOffset = useRef({ x: 0, y: 0 });
  const resizeStart = useRef({ width: 0, height: 0, mouseX: 0, mouseY: 0 });

  // Handle drag start from header
  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      // Don't start drag if clicking a button
      if ((e.target as HTMLElement).closest('button')) return;

      setIsDragging(true);
      dragOffset.current = {
        x: e.clientX - floatX,
        y: e.clientY - floatY,
      };
    },
    [floatX, floatY]
  );

  // Handle resize start from corner
  const handleResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setIsResizing(true);
      resizeStart.current = {
        width: floatWidth,
        height: floatHeight,
        mouseX: e.clientX,
        mouseY: e.clientY,
      };
    },
    [floatWidth, floatHeight]
  );

  // Global mouse move handler for drag and resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        // Calculate new position
        let newX = e.clientX - dragOffset.current.x;
        let newY = e.clientY - dragOffset.current.y;

        // Constrain to viewport
        const maxX = window.innerWidth - floatWidth;
        const maxY = window.innerHeight - floatHeight;
        newX = Math.max(0, Math.min(newX, maxX));
        newY = Math.max(0, Math.min(newY, maxY));

        setFloatPosition(newX, newY);
      }

      if (isResizing) {
        // Calculate new size
        const deltaX = e.clientX - resizeStart.current.mouseX;
        const deltaY = e.clientY - resizeStart.current.mouseY;
        let newWidth = resizeStart.current.width + deltaX;
        let newHeight = resizeStart.current.height + deltaY;

        // Enforce minimum sizes
        newWidth = Math.max(MIN_FLOAT_WIDTH, newWidth);
        newHeight = Math.max(MIN_FLOAT_HEIGHT, newHeight);

        // Enforce maximum sizes (80% of viewport)
        newWidth = Math.min(window.innerWidth * 0.8, newWidth);
        newHeight = Math.min(window.innerHeight * 0.8, newHeight);

        setFloatSize(newWidth, newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      setIsResizing(false);
    };

    if (isDragging || isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [
    isDragging,
    isResizing,
    floatWidth,
    floatHeight,
    setFloatPosition,
    setFloatSize,
  ]);

  // Handle minimize to hidden
  const handleMinimize = useCallback(() => {
    setPosition('hidden');
  }, [setPosition]);

  return (
    <div
      ref={panelRef}
      className="fixed z-40 flex flex-col rounded-lg border bg-background shadow-lg"
      style={{
        left: floatX,
        top: floatY,
        width: floatWidth,
        height: floatHeight,
      }}
      role="dialog"
      aria-label="Q&A Assistant"
    >
      {/* Draggable header */}
      <div
        className={`cursor-move ${isDragging ? 'cursor-grabbing' : ''}`}
        onMouseDown={handleDragStart}
      >
        <div className="flex items-center justify-between border-b p-3">
          <h2 className="text-sm font-semibold">Q&A Assistant</h2>
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleMinimize}
                  aria-label="Minimize panel"
                >
                  <Minimize2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Minimize</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <QAPanelPlaceholder />
      </div>

      {/* Resize handle in corner */}
      <div
        className="absolute bottom-0 right-0 flex h-4 w-4 cursor-se-resize items-center justify-center"
        onMouseDown={handleResizeStart}
        role="slider"
        aria-label="Resize panel"
        aria-valuemin={MIN_FLOAT_WIDTH}
        aria-valuemax={800}
        aria-valuenow={floatWidth}
        tabIndex={0}
      >
        <GripHorizontal className="h-4 w-4 rotate-[-45deg] text-muted-foreground" />
      </div>
    </div>
  );
}
