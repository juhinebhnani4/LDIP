'use client';

/**
 * LinkedLibraryPanel Component
 *
 * Displays library documents linked to the current matter.
 * Can be embedded in the matter workspace Documents tab.
 *
 * Phase 2: Shared Legal Library feature.
 *
 * @example
 * ```tsx
 * <LinkedLibraryPanel matterId="matter-123" />
 * ```
 */

import { useEffect, useState } from 'react';
import {
  BookOpen,
  ExternalLink,
  FileText,
  Gavel,
  Link2Off,
  Loader2,
  Plus,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useLibraryStore } from '@/stores/libraryStore';
import { LibraryBrowser } from './LibraryBrowser';
import type { LibraryDocumentListItem, LibraryDocumentType } from '@/types/library';

// =============================================================================
// Props
// =============================================================================

export interface LinkedLibraryPanelProps {
  /** Matter ID for context */
  matterId: string;
  /** Optional callback when a document is clicked */
  onDocumentClick?: (documentId: string) => void;
}

// =============================================================================
// Document Type Config
// =============================================================================

const DOCUMENT_TYPE_CONFIG: Record<
  LibraryDocumentType,
  { icon: typeof FileText; label: string; color: string }
> = {
  act: { icon: Gavel, label: 'Act', color: 'text-blue-600 dark:text-blue-400' },
  statute: { icon: BookOpen, label: 'Statute', color: 'text-purple-600 dark:text-purple-400' },
  judgment: { icon: Gavel, label: 'Judgment', color: 'text-amber-600 dark:text-amber-400' },
  regulation: { icon: FileText, label: 'Regulation', color: 'text-green-600 dark:text-green-400' },
  commentary: { icon: BookOpen, label: 'Commentary', color: 'text-gray-600 dark:text-gray-400' },
  circular: { icon: FileText, label: 'Circular', color: 'text-cyan-600 dark:text-cyan-400' },
};

// =============================================================================
// Sub-Components
// =============================================================================

function LoadingSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-3 p-2">
          <Skeleton className="h-8 w-8 rounded" />
          <div className="flex-1 space-y-1">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ onAddClick }: { onAddClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="rounded-full bg-muted p-3 mb-3">
        <BookOpen className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium mb-1">No library documents linked</p>
      <p className="text-xs text-muted-foreground mb-4">
        Link Acts, Statutes, or Judgments from the shared library
      </p>
      <Button variant="outline" size="sm" onClick={onAddClick}>
        <Plus className="h-4 w-4 mr-1" />
        Browse Library
      </Button>
    </div>
  );
}

interface LinkedDocumentItemProps {
  document: LibraryDocumentListItem;
  isUnlinking: boolean;
  onUnlink: () => void;
  onClick?: () => void;
}

function LinkedDocumentItem({
  document,
  isUnlinking,
  onUnlink,
  onClick,
}: LinkedDocumentItemProps) {
  // Safely get config with fallback for unknown document types
  const config = DOCUMENT_TYPE_CONFIG[document.documentType] || {
    icon: FileText,
    label: document.documentType || 'Document',
    color: 'text-gray-600 dark:text-gray-400',
  };
  const Icon = config.icon;

  return (
    <div
      className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors group cursor-pointer"
      onClick={onClick}
    >
      <div className={`flex-shrink-0 ${config.color}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{document.title}</p>
        <div className="flex items-center gap-1 mt-0.5">
          <Badge variant="outline" className="text-xs py-0 h-5">
            {config.label}
          </Badge>
          {document.year && (
            <span className="text-xs text-muted-foreground">{document.year}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {onClick && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => {
            e.stopPropagation();
            onClick();
          }}>
            <ExternalLink className="h-4 w-4" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-destructive hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            onUnlink();
          }}
          disabled={isUnlinking}
        >
          {isUnlinking ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Link2Off className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function LinkedLibraryPanel({
  matterId,
  onDocumentClick,
}: LinkedLibraryPanelProps) {
  const [browserOpen, setBrowserOpen] = useState(false);
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null);

  // Store selectors
  const linkedDocuments = useLibraryStore((state) => state.linkedDocuments);
  const isLoadingLinked = useLibraryStore((state) => state.isLoadingLinked);
  const error = useLibraryStore((state) => state.error);

  // Store actions
  const loadLinkedDocuments = useLibraryStore((state) => state.loadLinkedDocuments);
  const unlinkDocument = useLibraryStore((state) => state.unlinkDocument);
  const setMatterId = useLibraryStore((state) => state.setMatterId);

  // Load linked documents on mount
  useEffect(() => {
    if (matterId) {
      setMatterId(matterId);
      loadLinkedDocuments(matterId);
    }
  }, [matterId, setMatterId, loadLinkedDocuments]);

  const handleUnlink = async (documentId: string) => {
    setUnlinkingId(documentId);
    await unlinkDocument(documentId);
    setUnlinkingId(null);
  };

  const handleBrowserClose = (open: boolean) => {
    setBrowserOpen(open);
    // Refresh linked documents when browser closes
    if (!open && matterId) {
      loadLinkedDocuments(matterId);
    }
  };

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <BookOpen className="h-4 w-4" />
                Linked Library
              </CardTitle>
              <CardDescription className="text-xs mt-1">
                Shared legal documents linked to this matter
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => setBrowserOpen(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoadingLinked ? (
            <LoadingSkeleton />
          ) : error ? (
            <div className="text-center py-4">
              <p className="text-sm text-destructive mb-2">Failed to load</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadLinkedDocuments(matterId)}
              >
                Retry
              </Button>
            </div>
          ) : linkedDocuments.length === 0 ? (
            <EmptyState onAddClick={() => setBrowserOpen(true)} />
          ) : (
            <div className="space-y-1">
              {linkedDocuments.map((doc) => (
                <LinkedDocumentItem
                  key={doc.id}
                  document={doc}
                  isUnlinking={unlinkingId === doc.id}
                  onUnlink={() => handleUnlink(doc.id)}
                  onClick={onDocumentClick ? () => onDocumentClick(doc.id) : undefined}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <LibraryBrowser
        matterId={matterId}
        open={browserOpen}
        onOpenChange={handleBrowserClose}
      />
    </>
  );
}

export default LinkedLibraryPanel;
