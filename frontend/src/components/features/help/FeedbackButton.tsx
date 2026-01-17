'use client';

import { MessageSquarePlus, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface FeedbackButtonProps {
  variant?: 'icon' | 'full';
  className?: string;
}

function buildFeedbackUrl(): string {
  const baseUrl = 'https://github.com/your-org/ldip/issues/new';
  const params = new URLSearchParams({
    template: 'bug_report.md',
    title: '[Feedback] ',
  });

  // Add context if in browser
  if (typeof window !== 'undefined') {
    const body = `
## Describe the issue

<!-- Please describe your feedback here -->

---
**Context:**
- Page: ${window.location.pathname}
- Browser: ${navigator.userAgent}
- Timestamp: ${new Date().toISOString()}
`.trim();

    params.set('body', body);
  }

  return `${baseUrl}?${params.toString()}`;
}

export function FeedbackButton({ variant = 'icon', className }: FeedbackButtonProps) {
  const handleClick = () => {
    const url = buildFeedbackUrl();
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  if (variant === 'full') {
    return (
      <Button
        variant="outline"
        onClick={handleClick}
        className={className}
      >
        <MessageSquarePlus className="h-4 w-4 mr-2" />
        Send Feedback
        <ExternalLink className="h-3 w-3 ml-1 text-muted-foreground" />
      </Button>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleClick}
          aria-label="Send feedback"
          className={className}
        >
          <MessageSquarePlus className="h-5 w-5" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        <p>Send Feedback</p>
      </TooltipContent>
    </Tooltip>
  );
}
