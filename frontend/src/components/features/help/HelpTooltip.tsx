'use client';

import { HelpCircle } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface HelpTooltipProps {
  content: string;
  learnMoreId?: string;
  side?: 'top' | 'right' | 'bottom' | 'left';
  className?: string;
  iconClassName?: string;
}

export function HelpTooltip({
  content,
  learnMoreId,
  side = 'top',
  className,
  iconClassName,
}: HelpTooltipProps) {
  return (
    <Tooltip delayDuration={300}>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            'inline-flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 rounded-full',
            className
          )}
          aria-label="More information"
        >
          <HelpCircle className={cn('h-4 w-4', iconClassName)} />
        </button>
      </TooltipTrigger>
      <TooltipContent side={side} className="max-w-xs">
        <p className="text-sm">{content}</p>
        {learnMoreId && (
          <p className="text-xs text-muted-foreground mt-1">
            Press ? to learn more
          </p>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

interface HelpTooltipInlineProps {
  content: string;
  learnMoreId?: string;
}

export function HelpTooltipInline({ content, learnMoreId }: HelpTooltipInlineProps) {
  return (
    <HelpTooltip
      content={content}
      learnMoreId={learnMoreId}
      className="ml-1 align-middle"
      iconClassName="h-3.5 w-3.5"
    />
  );
}
