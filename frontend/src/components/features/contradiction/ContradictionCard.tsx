'use client';

/**
 * ContradictionCard Component
 *
 * Displays a single contradiction with type badge, severity indicator,
 * both statements, explanation, and evidence links.
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 4: Create ContradictionCard component
 */

import Link from 'next/link';
import { ExternalLink, CheckCircle2, AlertCircle, XCircle, User, Calendar, ChevronRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatementSection } from './StatementSection';
import { HelpTooltipInline } from '@/components/features/help';
import { getVerificationStatus, formatConfidenceTooltip } from '@/lib/utils/confidenceDisplay';
import type {
  ContradictionItem,
  ContradictionType,
  ContradictionSeverity,
} from '@/hooks/useContradictions';
import type { ContradictionContext } from '@/types/crossEngine';

interface ContradictionCardProps {
  /** Contradiction data */
  contradiction: ContradictionItem;
  /** Matter ID for cross-engine navigation */
  matterId?: string;
  /** Optional callback when document link is clicked */
  onDocumentClick?: (documentId: string, page: number | null) => void;
  /** Optional callback when evidence link is clicked */
  onEvidenceClick?: (documentId: string, page: number | null, bboxIds: string[]) => void;
  /** Gap 5-3: Cross-engine context data */
  crossEngineContext?: ContradictionContext | null;
  /** Gap 5-3: Whether to show cross-engine links */
  showCrossEngineLinks?: boolean;
}

/**
 * Get badge styling for contradiction type.
 */
function getTypeBadgeStyle(type: ContradictionType): string {
  switch (type) {
    case 'semantic_contradiction':
      return 'bg-purple-100 text-purple-800 border-purple-200';
    case 'factual_contradiction':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'date_mismatch':
      return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'amount_mismatch':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
}

/**
 * Get display label for contradiction type.
 */
function getTypeLabel(type: ContradictionType): string {
  switch (type) {
    case 'semantic_contradiction':
      return 'Semantic';
    case 'factual_contradiction':
      return 'Factual';
    case 'date_mismatch':
      return 'Date Mismatch';
    case 'amount_mismatch':
      return 'Amount Mismatch';
    default:
      return type;
  }
}

/**
 * Get severity indicator styling.
 */
function getSeverityStyle(severity: ContradictionSeverity): {
  bg: string;
  border: string;
  text: string;
  label: string;
} {
  switch (severity) {
    case 'high':
      return {
        bg: 'bg-red-100',
        border: 'border-l-red-500',
        text: 'text-red-800',
        label: 'High',
      };
    case 'medium':
      return {
        bg: 'bg-yellow-100',
        border: 'border-l-yellow-500',
        text: 'text-yellow-800',
        label: 'Medium',
      };
    case 'low':
      return {
        bg: 'bg-gray-100',
        border: 'border-l-gray-400',
        text: 'text-gray-600',
        label: 'Low',
      };
    default:
      return {
        bg: 'bg-gray-100',
        border: 'border-l-gray-400',
        text: 'text-gray-600',
        label: severity,
      };
  }
}

/**
 * ContradictionCard displays a single contradiction with full details.
 *
 * @example
 * ```tsx
 * <ContradictionCard
 *   contradiction={contradiction}
 *   onDocumentClick={(docId, page) => openPdfViewer(docId, page)}
 *   onEvidenceClick={(docId, page, bboxIds) => openSplitView(docId, page, bboxIds)}
 * />
 * ```
 */
export function ContradictionCard({
  contradiction,
  matterId,
  onDocumentClick,
  onEvidenceClick,
  crossEngineContext,
  showCrossEngineLinks = false,
}: ContradictionCardProps) {
  const severityStyle = getSeverityStyle(contradiction.severity);
  const typeBadgeStyle = getTypeBadgeStyle(contradiction.contradictionType);

  return (
    <Card className={`border-l-4 ${severityStyle.border} py-4`}>
      <CardContent className="space-y-4">
        {/* Header with type badge and severity */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Badge className={typeBadgeStyle} variant="outline">
              {getTypeLabel(contradiction.contradictionType)}
            </Badge>
            <Badge className={`${severityStyle.bg} ${severityStyle.text}`} variant="outline">
              {severityStyle.label} Severity
            </Badge>
          </div>
          {(() => {
            const status = getVerificationStatus(contradiction.confidence);
            const StatusIcon = status.level === 'verified' ? CheckCircle2 : status.level === 'likely_correct' ? AlertCircle : XCircle;
            return (
              <div
                className="flex items-center gap-1"
                title={formatConfidenceTooltip(contradiction.confidence)}
              >
                <Badge variant="outline" className={status.badgeClass}>
                  <StatusIcon className="h-3 w-3 mr-1" />
                  {status.label}
                </Badge>
                <HelpTooltipInline
                  content={`${status.label}: ${status.level === 'verified' ? 'High confidence finding, reliable for court use.' : status.level === 'likely_correct' ? 'Review recommended before relying on this finding.' : 'Requires attorney verification before use.'}`}
                  learnMoreId="confidence-scores"
                />
              </div>
            );
          })()}
        </div>

        {/* Statements */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <StatementSection
            statement={contradiction.statementA}
            label="Statement A"
            onDocumentClick={onDocumentClick}
          />
          <StatementSection
            statement={contradiction.statementB}
            label="Statement B"
            onDocumentClick={onDocumentClick}
          />
        </div>

        {/* Explanation */}
        <div className="pt-2 border-t">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
            Explanation
          </div>
          <p className="text-sm">{contradiction.explanation}</p>
        </div>

        {/* Evidence links */}
        {contradiction.evidenceLinks.length > 0 && (
          <div className="pt-2 border-t">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
              Evidence
            </div>
            <div className="flex flex-wrap gap-2">
              {contradiction.evidenceLinks.map((link) => (
                <Button
                  key={link.statementId}
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() =>
                    onEvidenceClick?.(link.documentId, link.page, link.bboxIds)
                  }
                >
                  <ExternalLink className="h-3 w-3 mr-1" />
                  {link.documentName}
                  {link.page !== null && ` (p. ${link.page})`}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Gap 5-3: Cross-Engine Links */}
        {showCrossEngineLinks && matterId && (
          <div className="pt-2 border-t">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
              Related Context
            </div>
            <div className="flex flex-wrap gap-3">
              {/* Entity Link */}
              <Link
                href={`/matter/${matterId}/entities?entity=${contradiction.entityId}`}
                className="inline-flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-800 dark:text-purple-400 dark:hover:text-purple-300"
              >
                <User className="h-3.5 w-3.5" />
                <span>View {contradiction.entityName}</span>
                <ChevronRight className="h-3 w-3 opacity-50" />
              </Link>

              {/* Timeline Events Link */}
              {crossEngineContext && crossEngineContext.relatedEvents.length > 0 && (
                <Link
                  href={`/matter/${matterId}/timeline?entity=${contradiction.entityId}`}
                  className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                >
                  <Calendar className="h-3.5 w-3.5" />
                  <span>{crossEngineContext.relatedEvents.length} Timeline Events</span>
                  <ChevronRight className="h-3 w-3 opacity-50" />
                </Link>
              )}
            </div>

            {/* Show preview of related timeline events */}
            {crossEngineContext && crossEngineContext.relatedEvents.length > 0 && (
              <div className="mt-2 space-y-1">
                {crossEngineContext.relatedEvents.slice(0, 2).map((event) => (
                  <Link
                    key={event.eventId}
                    href={`/matter/${matterId}/timeline?event=${event.eventId}`}
                    className="block p-2 rounded bg-muted/50 text-xs hover:bg-muted transition-colors"
                  >
                    <span className="font-medium">{event.eventDate}</span>
                    <span className="text-muted-foreground"> - </span>
                    <span className="truncate">{event.description.slice(0, 60)}...</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
