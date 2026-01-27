'use client';

/**
 * CrossEngineLinks Component
 *
 * Gap 5-3: Cross-Engine Correlation Links
 *
 * Reusable component for displaying cross-engine navigation links
 * with counts and badges.
 */

import Link from 'next/link';
import {
  Calendar,
  Users,
  AlertTriangle,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

export interface CrossEngineLinkProps {
  /** Type of link */
  type: 'timeline' | 'entities' | 'contradictions';
  /** Matter ID for navigation */
  matterId: string;
  /** Target ID (entity, event, or contradiction) */
  targetId?: string;
  /** Count to display in badge */
  count?: number;
  /** High severity count (for contradictions) */
  highSeverityCount?: number;
  /** Label to display */
  label?: string;
  /** Size variant */
  size?: 'sm' | 'default';
  /** Custom className */
  className?: string;
}

// =============================================================================
// Icon Mapping
// =============================================================================

const ICONS = {
  timeline: Calendar,
  entities: Users,
  contradictions: AlertTriangle,
};

const LABELS = {
  timeline: 'Timeline Events',
  entities: 'Entities',
  contradictions: 'Contradictions',
};

const COLORS = {
  timeline: 'text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300',
  entities: 'text-purple-600 hover:text-purple-800 dark:text-purple-400 dark:hover:text-purple-300',
  contradictions: 'text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300',
};

// =============================================================================
// CrossEngineLink Component
// =============================================================================

/**
 * Single cross-engine link with optional count badge
 */
export function CrossEngineLink({
  type,
  matterId,
  targetId,
  count,
  highSeverityCount,
  label,
  size = 'default',
  className,
}: CrossEngineLinkProps) {
  const Icon = ICONS[type];
  const displayLabel = label ?? LABELS[type];

  // Build the href
  let href = `/matter/${matterId}/${type}`;
  if (targetId) {
    if (type === 'entities') {
      href += `?entity=${targetId}`;
    } else if (type === 'timeline') {
      href += `?event=${targetId}`;
    } else if (type === 'contradictions') {
      href += `?contradiction=${targetId}`;
    }
  }

  const isSmall = size === 'sm';
  const hasHighSeverity = highSeverityCount && highSeverityCount > 0;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          href={href}
          className={cn(
            'inline-flex items-center gap-1.5 transition-colors',
            COLORS[type],
            isSmall ? 'text-xs' : 'text-sm',
            className
          )}
        >
          <Icon className={cn(isSmall ? 'h-3 w-3' : 'h-4 w-4')} aria-hidden="true" />
          <span>{displayLabel}</span>
          {count !== undefined && count > 0 && (
            <Badge
              variant={hasHighSeverity ? 'destructive' : 'secondary'}
              className={cn(
                'ml-1',
                isSmall ? 'text-[10px] px-1 py-0' : 'text-xs px-1.5 py-0'
              )}
            >
              {count}
              {hasHighSeverity && (
                <AlertCircle className="h-2.5 w-2.5 ml-0.5" aria-hidden="true" />
              )}
            </Badge>
          )}
          <ChevronRight
            className={cn(
              'opacity-50',
              isSmall ? 'h-3 w-3' : 'h-4 w-4'
            )}
            aria-hidden="true"
          />
        </Link>
      </TooltipTrigger>
      <TooltipContent>
        <p>
          View {displayLabel.toLowerCase()}
          {count !== undefined && ` (${count} ${count === 1 ? 'item' : 'items'})`}
        </p>
        {hasHighSeverity && (
          <p className="text-destructive">
            {highSeverityCount} high severity
          </p>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

// =============================================================================
// CrossEngineLinkGroup Component
// =============================================================================

export interface CrossEngineLinkGroupProps {
  /** Matter ID for navigation */
  matterId: string;
  /** Links to display */
  links: Array<{
    type: 'timeline' | 'entities' | 'contradictions';
    targetId?: string;
    count?: number;
    highSeverityCount?: number;
    label?: string;
  }>;
  /** Size variant */
  size?: 'sm' | 'default';
  /** Direction of links */
  direction?: 'horizontal' | 'vertical';
  /** Custom className */
  className?: string;
}

/**
 * Group of cross-engine links
 */
export function CrossEngineLinkGroup({
  matterId,
  links,
  size = 'default',
  direction = 'horizontal',
  className,
}: CrossEngineLinkGroupProps) {
  const filteredLinks = links.filter(
    (link) => link.count === undefined || link.count > 0
  );

  if (filteredLinks.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'flex',
        direction === 'horizontal' ? 'flex-wrap items-center gap-3' : 'flex-col gap-2',
        className
      )}
    >
      {filteredLinks.map((link, index) => (
        <CrossEngineLink
          key={`${link.type}-${link.targetId ?? index}`}
          matterId={matterId}
          type={link.type}
          targetId={link.targetId}
          count={link.count}
          highSeverityCount={link.highSeverityCount}
          label={link.label}
          size={size}
        />
      ))}
    </div>
  );
}

// =============================================================================
// CrossEngineButton Component
// =============================================================================

export interface CrossEngineButtonProps {
  /** Type of link */
  type: 'timeline' | 'entities' | 'contradictions';
  /** Matter ID for navigation */
  matterId: string;
  /** Target ID */
  targetId?: string;
  /** Count to display */
  count?: number;
  /** High severity count */
  highSeverityCount?: number;
  /** Button variant */
  variant?: 'default' | 'outline' | 'ghost';
  /** Size variant */
  size?: 'sm' | 'default';
  /** Custom className */
  className?: string;
}

/**
 * Button variant for cross-engine navigation
 */
export function CrossEngineButton({
  type,
  matterId,
  targetId,
  count,
  highSeverityCount,
  variant = 'outline',
  size = 'sm',
  className,
}: CrossEngineButtonProps) {
  const Icon = ICONS[type];
  const displayLabel = LABELS[type];

  let href = `/matter/${matterId}/${type}`;
  if (targetId) {
    if (type === 'entities') {
      href += `?entity=${targetId}`;
    } else if (type === 'timeline') {
      href += `?event=${targetId}`;
    } else if (type === 'contradictions') {
      href += `?contradiction=${targetId}`;
    }
  }

  const hasHighSeverity = highSeverityCount && highSeverityCount > 0;

  return (
    <Button
      variant={variant}
      size={size}
      className={cn('gap-1.5', className)}
      asChild
    >
      <Link href={href}>
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        <span>{displayLabel}</span>
        {count !== undefined && count > 0 && (
          <Badge
            variant={hasHighSeverity ? 'destructive' : 'secondary'}
            className="ml-1 text-[10px] px-1 py-0"
          >
            {count}
          </Badge>
        )}
      </Link>
    </Button>
  );
}
