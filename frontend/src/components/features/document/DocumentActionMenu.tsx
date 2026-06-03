'use client';

import { Eye, FileText, MoreVertical, Pencil, RefreshCw, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { DocumentListItem, DocumentStatus } from '@/types/document';
import type { MatterRole } from '@/types/matter';

/** Statuses where retry should be available */
const RETRYABLE_STATUSES: DocumentStatus[] = [
  'failed', 'ocr_failed', 'chunking_failed', 'embedding_failed',  // all failure states
  'ocr_complete',  // stuck: OCR done but RAG never started
  'processing', 'pending',  // stuck: never progressed
];

export interface DocumentActionMenuProps {
  document: DocumentListItem;
  onView: () => void;
  onRename: () => void;
  onSetAsAct: () => void;
  onSetAsCaseFile?: () => void;
  onDelete: () => void;
  onRetry?: () => void;
  userRole?: MatterRole;
  disabled?: boolean;
}

/**
 * Dropdown action menu for document management.
 *
 * Provides View, Rename, Set as Act, and Delete actions.
 * Role-based visibility: Delete is only shown for OWNER role.
 * Set as Act is hidden if document is already an act.
 */
export function DocumentActionMenu({
  document,
  onView,
  onRename,
  onSetAsAct,
  onSetAsCaseFile,
  onDelete,
  onRetry,
  userRole = 'editor',
  disabled = false,
}: DocumentActionMenuProps) {
  const isAct = document.documentType === 'act';
  // Allow delete for both owner and editor roles
  const canDelete = userRole === 'owner' || userRole === 'editor';
  const canEdit = userRole === 'owner' || userRole === 'editor';

  // Show retry option for failed or stuck documents
  const canRetry = onRetry && canEdit && RETRYABLE_STATUSES.includes(document.status);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label={`Actions for ${document.filename}`}
          disabled={disabled}
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={onView}>
          <Eye className="mr-2 h-4 w-4" />
          View
        </DropdownMenuItem>
        {canEdit && (
          <DropdownMenuItem onClick={onRename}>
            <Pencil className="mr-2 h-4 w-4" />
            Rename
          </DropdownMenuItem>
        )}
        {canEdit && !isAct && (
          <DropdownMenuItem onClick={onSetAsAct}>
            <FileText className="mr-2 h-4 w-4" />
            Set as Act
          </DropdownMenuItem>
        )}
        {canEdit && isAct && onSetAsCaseFile && (
          <DropdownMenuItem onClick={onSetAsCaseFile}>
            <FileText className="mr-2 h-4 w-4" />
            Set as Case File
          </DropdownMenuItem>
        )}
        {canRetry && (
          <DropdownMenuItem onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry Processing
          </DropdownMenuItem>
        )}
        {canDelete && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={onDelete}
              variant="destructive"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
