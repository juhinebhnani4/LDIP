'use client';

import { MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useQAPanelStore } from '@/stores/qaPanelStore';

/**
 * Q&A Panel Expand Button
 *
 * Fixed button shown when Q&A panel is hidden. Clicking restores
 * the panel to its previous non-hidden position.
 *
 * Features:
 * - Fixed position in bottom-right corner
 * - Badge showing unread message count (mock for MVP)
 * - Tooltip explaining functionality
 * - Click restores panel to previous position
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 */
export function QAPanelExpandButton() {
  const unreadCount = useQAPanelStore((state) => state.unreadCount);
  const restoreFromHidden = useQAPanelStore((state) => state.restoreFromHidden);

  return (
    <div className="fixed bottom-4 right-4 z-30">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="default"
            size="icon"
            className="relative h-12 w-12 rounded-full shadow-lg"
            onClick={restoreFromHidden}
            aria-label="Open Q&A Panel"
          >
            <MessageSquare className="h-5 w-5" />
            {unreadCount > 0 && (
              <Badge
                variant="destructive"
                className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full p-0 text-xs"
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </Badge>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent side="left">
          <p>Open Q&A Panel</p>
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
