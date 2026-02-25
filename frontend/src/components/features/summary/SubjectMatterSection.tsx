'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { FileText, ExternalLink } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { InlineVerificationButtons } from './InlineVerificationButtons';
import { VerificationBadge } from './VerificationBadge';
import { SummaryNotesDialog } from './SummaryNotesDialog';
import { EditableSection } from './EditableSection';
import { CitationLink } from './CitationLink';
import { openDocumentByName } from '@/lib/utils/openDocument';
import type { SubjectMatter, SummaryVerificationDecision } from '@/types/summary';

/**
 * Subject Matter Section Component
 *
 * Displays the AI-generated subject matter description with source citations.
 * Now includes inline verification buttons on hover.
 *
 * Story 10B.1: Summary Tab Content (AC #1)
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 * Story 14.6: Integrated EditableSection and CitationLink (AC #1, #4)
 */

interface SubjectMatterSectionProps {
  /** Subject matter data */
  subjectMatter: SubjectMatter;
  /** Optional className for styling */
  className?: string;
  /** Callback when section is verified */
  onVerify?: () => Promise<void>;
  /** Callback when section is flagged */
  onFlag?: () => Promise<void>;
  /** Callback when note is saved */
  onSaveNote?: (note: string) => Promise<void>;
  /** Callback when content is saved (Story 14.6) */
  onSave?: (newContent: string) => Promise<void>;
  /** Callback to regenerate content (Story 14.6) */
  onRegenerate?: () => Promise<void>;
  /** Callback to open document in split view instead of new tab (BBOX-7) */
  onViewSource?: (documentName: string, page?: number) => void;
}

export function SubjectMatterSection({
  subjectMatter,
  className,
  onVerify,
  onFlag,
  onSaveNote,
  onSave,
  onRegenerate,
  onViewSource,
}: SubjectMatterSectionProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;
  const [isHovered, setIsHovered] = useState(false);
  const [isNotesDialogOpen, setIsNotesDialogOpen] = useState(false);
  const [verificationDecision, setVerificationDecision] = useState<SummaryVerificationDecision | undefined>(
    subjectMatter.isVerified ? 'verified' : undefined
  );

  // Story 14.6: Use edited content if available, otherwise use AI-generated
  const displayContent = subjectMatter.editedContent ?? subjectMatter.description;

  const handleVerify = async () => {
    if (onVerify) {
      await onVerify();
      setVerificationDecision('verified');
    }
  };

  const handleFlag = async () => {
    if (onFlag) {
      await onFlag();
      setVerificationDecision('flagged');
    }
  };

  const handleSaveNote = async (note: string) => {
    if (onSaveNote) {
      await onSaveNote(note);
    }
  };

  // Story 14.6: Handle save and regenerate
  const handleSave = async (newContent: string) => {
    if (onSave) {
      await onSave(newContent);
    }
  };

  const handleRegenerate = async () => {
    if (onRegenerate) {
      await onRegenerate();
    }
  };

  // Story 14.6: Content renderer with CitationLinks
  // Updated to render markdown for structured case overviews
  const renderContent = () => (
    <>
      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-0.5 prose-strong:text-foreground">
        <ReactMarkdown>{displayContent}</ReactMarkdown>
      </div>

      {/* Story 14.6: Citation links for factual claims */}
      {subjectMatter.citations && subjectMatter.citations.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {subjectMatter.citations.map((citation, index) => {
            // When page is null, use a short excerpt snippet as display text
            // so multiple citations from the same document are distinguishable
            const fallbackText =
              citation.page == null && citation.excerpt
                ? citation.excerpt.slice(0, 40) + (citation.excerpt.length > 40 ? '\u2026' : '')
                : undefined;

            return (
              <CitationLink
                key={`citation-${index}`}
                documentName={citation.documentName}
                pageNumber={citation.page}
                excerpt={citation.excerpt}
                displayText={fallbackText}
                className="text-xs"
                onViewSource={onViewSource}
              />
            );
          })}
        </div>
      )}

      {/* Source citations */}
      {subjectMatter.sources.length > 0 && (
        <div className="mt-4 pt-4 border-t">
          <p className="text-xs text-muted-foreground mb-2">Sources:</p>
          <div className="flex flex-wrap gap-2">
            {subjectMatter.sources.map((source, index) => (
              <Button
                key={`${source.documentName}-${index}`}
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => onViewSource
                  ? onViewSource(source.documentName, Number(source.pageRange.split('-')[0]) || undefined)
                  : openDocumentByName(matterId, source.documentName, source.pageRange.split('-')[0])
                }
                aria-label={`View source: ${source.documentName}, pages ${source.pageRange}`}
              >
                <ExternalLink className="h-3 w-3 mr-1" aria-hidden="true" />
                {source.documentName} (pp. {source.pageRange})
              </Button>
            ))}
          </div>
        </div>
      )}
    </>
  );

  return (
    <section className={className} aria-labelledby="subject-matter-heading">
      <h2 id="subject-matter-heading" className="text-lg font-semibold mb-4">
        Subject Matter
      </h2>
      <Card
        className="relative"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <CardTitle className="text-base">Case Overview</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <InlineVerificationButtons
                sectionType="subject_matter"
                sectionId={matterId}
                currentDecision={verificationDecision}
                onVerify={handleVerify}
                onFlag={handleFlag}
                onAddNote={() => setIsNotesDialogOpen(true)}
                isVisible={isHovered}
              />
              <VerificationBadge decision={verificationDecision} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          {/* Story 14.6: Wrap content in EditableSection if edit handlers provided */}
          {onSave && onRegenerate ? (
            <EditableSection
              sectionType="subject_matter"
              sectionId="main"
              content={displayContent}
              originalContent={subjectMatter.description}
              onSave={handleSave}
              onRegenerate={handleRegenerate}
            >
              {renderContent()}
            </EditableSection>
          ) : (
            renderContent()
          )}
        </CardContent>
      </Card>

      <SummaryNotesDialog
        isOpen={isNotesDialogOpen}
        onClose={() => setIsNotesDialogOpen(false)}
        onSave={handleSaveNote}
        sectionType="subject_matter"
        sectionId={matterId}
      />
    </section>
  );
}

/**
 * Subject Matter Section Skeleton
 */
export function SubjectMatterSectionSkeleton({ className }: { className?: string }) {
  return (
    <section className={className}>
      <Skeleton className="h-6 w-32 mb-4" />
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-5" />
              <Skeleton className="h-5 w-28" />
            </div>
            <Skeleton className="h-5 w-24" />
          </div>
        </CardHeader>
        <CardContent className="pt-2 space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <div className="pt-4 border-t mt-4">
            <Skeleton className="h-3 w-16 mb-2" />
            <div className="flex gap-2">
              <Skeleton className="h-7 w-36" />
              <Skeleton className="h-7 w-32" />
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
