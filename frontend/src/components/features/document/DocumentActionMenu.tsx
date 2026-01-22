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
import type { DocumentListItem } from '@/types/document';
import type { MatterRole } from '@/types/matter';

export interface DocumentActionMenuProps {
  document: DocumentListItem;
  onView: () => void;
  onRename: () => void;
  onSetAsAct: () => void;
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
  const canRetry =
    onRetry &&
    canEdit &&
    (document.status === 'ocr_failed' ||
      document.status === 'ocr_complete' ||
      document.status === 'processing');

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
