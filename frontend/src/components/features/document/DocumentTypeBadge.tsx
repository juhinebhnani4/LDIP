'use client';

import type { DocumentType } from '@/types/document';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface DocumentTypeBadgeProps {
  type: DocumentType;
  className?: string;
}

const TYPE_CONFIG: Record<
  DocumentType,
  { label: string; className: string }
> = {
  case_file: {
    label: 'Case File',
    className: 'bg-blue-100 text-blue-800 border-blue-200 hover:bg-blue-200',
  },
  act: {
    label: 'Act',
    className: 'bg-green-100 text-green-800 border-green-200 hover:bg-green-200',
  },
  annexure: {
    label: 'Annexure',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-200 hover:bg-yellow-200',
  },
  other: {
    label: 'Other',
    className: 'bg-gray-100 text-gray-800 border-gray-200 hover:bg-gray-200',
  },
};

/**
 * Color-coded badge for document types
 *
 * Colors:
 * - case_file: blue
 * - act: green
 * - annexure: yellow
 * - other: gray
 */
export function DocumentTypeBadge({ type, className }: DocumentTypeBadgeProps) {
  const config = TYPE_CONFIG[type];

  return (
    <Badge
      variant="outline"
      className={cn(config.className, className)}
    >
      {config.label}
    </Badge>
  );
}
