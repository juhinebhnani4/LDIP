'use client';

import { useState } from 'react';
import {
  Check,
  EyeOff,
  Loader2,
  Minus,
  Move,
  PanelBottom,
  PanelRight,
  Settings2,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
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
import { clearChatCache } from '@/lib/api/chat';

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

interface QAPanelHeaderProps {
  /** Matter ID for cache operations */
  matterId?: string;
}

export function QAPanelHeader({ matterId }: QAPanelHeaderProps) {
  const position = useQAPanelStore((state) => state.position);
  const setPosition = useQAPanelStore((state) => state.setPosition);
  const [isClearingCache, setIsClearingCache] = useState(false);

  const handleMinimize = () => {
    setPosition('hidden');
  };

  const handleClearCache = async () => {
    if (!matterId) {
      toast.error('No matter selected');
      return;
    }

    setIsClearingCache(true);
    try {
      const result = await clearChatCache(matterId);
      toast.success('Cache cleared', {
        description: `Cleared ${result.query_cache_cleared} cached queries`,
      });
    } catch (error) {
      toast.error('Failed to clear cache', {
        description: error instanceof Error ? error.message : 'An error occurred',
      });
    } finally {
      setIsClearingCache(false);
    }
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
            <Button variant="ghost" size="icon" aria-label="Panel settings">
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
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Cache</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={handleClearCache}
              disabled={isClearingCache || !matterId}
            >
              {isClearingCache ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              Clear Cache
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
