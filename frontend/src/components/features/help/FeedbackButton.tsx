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
  let subject = '[Feedback] ';
  let body = 'Please describe your feedback here.\n';

  // Add context if in browser
  if (typeof window !== 'undefined') {
    subject += `(${window.location.pathname})`;
    body += `\n---\nPage: ${window.location.pathname}\nTimestamp: ${new Date().toISOString()}`;
  }

  const params = new URLSearchParams({ subject, body });
  return `mailto:support@jaanch.ai?${params.toString()}`;
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
