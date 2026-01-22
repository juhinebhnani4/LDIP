'use client';

import { Bug } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useInspectorStore } from '@/stores/inspectorStore';
import { cn } from '@/lib/utils';

/**
 * Debug Toggle Button
 *
 * A small toggle button that can be placed in the chat header
 * to enable/disable debug mode for showing search internals.
 *
 * Story: RAG Production Gaps - Feature 3: Inspector Mode
 */
export function DebugToggle() {
  const debugEnabled = useInspectorStore((state) => state.debugEnabled);
  const toggleDebug = useInspectorStore((state) => state.toggleDebug);
  const inspectorEnabled = useInspectorStore((state) => state.inspectorEnabled);

  // Don't show if inspector is disabled on the server
  if (!inspectorEnabled) {
    return null;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleDebug}
          aria-label={debugEnabled ? 'Disable debug mode' : 'Enable debug mode'}
          className={cn(
            'h-8 w-8',
            debugEnabled && 'bg-amber-100 text-amber-700 hover:bg-amber-200'
          )}
        >
          <Bug className="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        <p>{debugEnabled ? 'Hide debug info' : 'Show debug info'}</p>
      </TooltipContent>
    </Tooltip>
  );
}
