'use client';

import { useState, useEffect, useCallback } from 'react';
import { HelpCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { HelpPanel } from './HelpPanel';

interface HelpButtonProps {
  className?: string;
  'data-tour'?: string;
}

export function HelpButton({ className, 'data-tour': dataTour }: HelpButtonProps) {
  const [helpOpen, setHelpOpen] = useState(false);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // ? key (shift + /) opens help when not in an input
      if (
        e.key === '?' &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement) &&
        !(e.target as HTMLElement)?.isContentEditable
      ) {
        e.preventDefault();
        setHelpOpen(true);
      }
      // F1 also opens help
      if (e.key === 'F1') {
        e.preventDefault();
        setHelpOpen(true);
      }
      // Escape closes help
      if (e.key === 'Escape' && helpOpen) {
        setHelpOpen(false);
      }
    },
    [helpOpen]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setHelpOpen(true)}
            aria-label="Help"
            className={className}
            data-tour={dataTour}
          >
            <HelpCircle className="h-5 w-5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>Help (press ?)</p>
        </TooltipContent>
      </Tooltip>

      <HelpPanel open={helpOpen} onOpenChange={setHelpOpen} />
    </>
  );
}
