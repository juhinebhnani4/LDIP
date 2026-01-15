/**
 * EngineTrace Component
 *
 * Displays collapsible engine execution trace below responses.
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 7: Create EngineTrace component (AC: #2-3)
 *
 * Features:
 * - Collapsible trace section
 * - Engine icon, name, execution time, findings count
 * - Total processing time
 * - Subtle styling with muted colors
 */

'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Clock,
  FileSearch,
  Calendar,
  AlertTriangle,
  Search,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { EngineTraceData } from '@/hooks/useSSE';

interface EngineTraceProps {
  /** Engine execution traces */
  traces: EngineTraceData[];
  /** Total processing time in ms */
  totalTimeMs: number;
  /** Optional CSS classes */
  className?: string;
}

/** Engine type to icon mapping */
const ENGINE_ICONS: Record<string, typeof FileSearch> = {
  citation: FileSearch,
  timeline: Calendar,
  contradiction: AlertTriangle,
  rag: Search,
};

/** Engine type to display name mapping */
const ENGINE_LABELS: Record<string, string> = {
  citation: 'Citation Verification',
  timeline: 'Timeline Analysis',
  contradiction: 'Contradiction Detection',
  rag: 'Document Search',
};

/**
 * EngineTrace Component
 *
 * Story 11.3: Task 7.1-7.6 - Collapsible trace display.
 *
 * Shows engine execution details in a collapsible panel:
 * - Summary line with total time and engine count
 * - Expandable details showing each engine's performance
 * - Visual indicators for success/failure
 *
 * @example
 * <EngineTrace
 *   traces={[
 *     { engine: 'citation', executionTimeMs: 150, findingsCount: 3, success: true },
 *     { engine: 'rag', executionTimeMs: 200, findingsCount: 10, success: true },
 *   ]}
 *   totalTimeMs={350}
 * />
 */
export function EngineTrace({ traces, totalTimeMs, className }: EngineTraceProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Don't render if no traces
  if (!traces || traces.length === 0) {
    return null;
  }

  const successCount = traces.filter((t) => t.success).length;
  const totalFindings = traces.reduce((sum, t) => sum + t.findingsCount, 0);

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn('mt-2', className)}
      data-testid="engine-trace"
    >
      {/* Task 7.2: Collapsible trigger with summary */}
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
          aria-expanded={isOpen}
          aria-label={`Engine trace: ${totalTimeMs}ms, ${traces.length} engines. Click to ${isOpen ? 'collapse' : 'expand'}`}
        >
          <Clock className="mr-1 h-3 w-3" aria-hidden="true" />
          <span>{totalTimeMs}ms</span>
          <span className="mx-1" aria-hidden="true">
            ·
          </span>
          <span>
            {traces.length} engine{traces.length !== 1 ? 's' : ''}
          </span>
          {totalFindings > 0 && (
            <>
              <span className="mx-1" aria-hidden="true">
                ·
              </span>
              <span>{totalFindings} findings</span>
            </>
          )}
          {isOpen ? (
            <ChevronUp className="ml-1 h-3 w-3" aria-hidden="true" />
          ) : (
            <ChevronDown className="ml-1 h-3 w-3" aria-hidden="true" />
          )}
        </Button>
      </CollapsibleTrigger>

      {/* Task 7.3-7.5: Expanded trace details */}
      <CollapsibleContent className="mt-2">
        <div
          className="space-y-1 rounded-md bg-muted/50 p-2"
          role="list"
          aria-label="Engine execution details"
        >
          {traces.map((trace, index) => {
            const Icon = ENGINE_ICONS[trace.engine] || Search;
            const label = ENGINE_LABELS[trace.engine] || trace.engine;

            return (
              <div
                key={`${trace.engine}-${index}`}
                className={cn(
                  'flex items-center justify-between text-xs',
                  trace.success ? 'text-muted-foreground' : 'text-destructive'
                )}
                role="listitem"
              >
                {/* Engine name and icon */}
                <div className="flex items-center gap-1.5">
                  {trace.success ? (
                    <CheckCircle2
                      className="h-3 w-3 text-green-500"
                      aria-label="Success"
                    />
                  ) : (
                    <XCircle className="h-3 w-3 text-destructive" aria-label="Failed" />
                  )}
                  <Icon className="h-3 w-3" aria-hidden="true" />
                  <span>{label}</span>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-3">
                  <span>
                    {trace.findingsCount} finding{trace.findingsCount !== 1 ? 's' : ''}
                  </span>
                  <span className="text-muted-foreground/70 tabular-nums">
                    {trace.executionTimeMs}ms
                  </span>
                </div>
              </div>
            );
          })}

          {/* Summary row */}
          <div className="mt-1 flex items-center justify-between border-t border-border/50 pt-1 text-xs font-medium">
            <span>
              Total ({successCount}/{traces.length} successful)
            </span>
            <span className="tabular-nums">{totalTimeMs}ms</span>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
