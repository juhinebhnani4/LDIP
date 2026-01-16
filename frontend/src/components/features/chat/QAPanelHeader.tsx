'use client';

import {
  Check,
  EyeOff,
  Minus,
  Move,
  PanelBottom,
  PanelRight,
  Settings2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { JaanchIcon } from '@/components/ui/jaanch-logo';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useQAPanelStore } from '@/stores/qaPanelStore';
import type { QAPanelPosition } from '@/stores/qaPanelStore';

/**
 * Q&A Panel Header
 *
 * Header component for the Q&A panel with position controls.
 * Allows users to switch between right sidebar, bottom panel,
 * floating window, and hidden modes. Includes built-in minimize
 * button that works in all panel positions.
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 * Story 11.1: Updated title with jaanch.ai icon and added minimize button
 */

const POSITION_OPTIONS: Array<{
  value: QAPanelPosition;
  label: string;
  icon: typeof PanelRight;
  separator?: boolean;
}> = [
  { value: 'right', label: 'Right Sidebar', icon: PanelRight },
  { value: 'bottom', label: 'Bottom Panel', icon: PanelBottom },
  { value: 'float', label: 'Floating', icon: Move },
  { value: 'hidden', label: 'Hide Panel', icon: EyeOff, separator: true },
];

export function QAPanelHeader() {
  const position = useQAPanelStore((state) => state.position);
  const setPosition = useQAPanelStore((state) => state.setPosition);

  const handleMinimize = () => {
    setPosition('hidden');
  };

  return (
    <div className="flex items-center justify-between border-b p-3">
      <div className="flex items-center gap-2">
        <JaanchIcon size="xs" />
        <h2 className="text-sm font-semibold">Ask jaanch</h2>
      </div>
      <div className="flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleMinimize}
              aria-label="Minimize panel"
            >
              <Minus className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Minimize</p>
          </TooltipContent>
        </Tooltip>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Panel position">
              <Settings2 className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Panel Position</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {POSITION_OPTIONS.map((option) => (
              <div key={option.value}>
                {option.separator && <DropdownMenuSeparator />}
                <DropdownMenuItem onClick={() => setPosition(option.value)}>
                  <option.icon className="mr-2 h-4 w-4" />
                  {option.label}
                  {position === option.value && (
                    <Check className="ml-auto h-4 w-4" />
                  )}
                </DropdownMenuItem>
              </div>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
