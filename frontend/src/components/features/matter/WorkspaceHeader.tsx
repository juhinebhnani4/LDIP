'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';
import { EditableMatterName } from './EditableMatterName';
import { ExportDropdown } from './ExportDropdown';
import { ShareDialog } from './ShareDialog';
import { DeleteMatterDialog } from './DeleteMatterDialog';
import { MatterSettingsDialog } from './MatterSettingsDialog';
import { useMatterStore } from '@/stores/matterStore';
import { mattersApi } from '@/lib/api/matters';
import { ProcessingStatusBadge } from '@/components/features/processing/ProcessingStatusWidget';
import { ConsistencyWarningBadge } from '@/components/features/crossEngine/ConsistencyWarningBadge';

/**
 * Workspace Header Component
 *
 * Layout from UX-Decisions-Log.md:
 * ┌─────────────────────────────────────────────────────────────────────────────────┐
 * │  WORKSPACE HEADER                                                                │
 * │  ┌─────────────────┐                                      ┌────┐ ┌────┐ ┌────┐  │
 * │  │ ← Dashboard     │        [Matter Name]                 │ ⬇  │ │ 👥 │ │ ⚙  │  │
 * │  │                 │                                      │Exp │ │Shr │ │Set │  │
 * │  └─────────────────┘                                      └────┘ └────┘ └────┘  │
 * └─────────────────────────────────────────────────────────────────────────────────┘
 *
 * Story 10A.1: Workspace Shell Header
 */

interface WorkspaceHeaderProps {
  /** Matter ID for the current workspace */
  matterId: string;
}

export function WorkspaceHeader({ matterId }: WorkspaceHeaderProps) {
  const router = useRouter();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const currentMatter = useMatterStore((state) => state.currentMatter);
  const deleteMatter = useMatterStore((state) => state.deleteMatter);

  const handleDeleteMatter = async () => {
    try {
      await mattersApi.delete(matterId);
      deleteMatter(matterId);
      toast.success('Matter deleted successfully');
      router.push('/');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete matter';
      toast.error(message);
      throw err; // Re-throw to let dialog handle error state
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60" data-testid="workspace-header">
      <div className="container flex h-14 items-center gap-4 px-4 sm:px-6">
        {/* Left: Back navigation */}
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Back to Dashboard"
            data-testid="workspace-back-link"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="text-sm font-medium">Dashboard</span>
          </Link>
        </div>

        {/* Center: Editable matter name */}
        <div className="flex-1 flex justify-center px-4">
          <EditableMatterName matterId={matterId} />
        </div>

        {/* Status badges: Processing and Consistency (Story 5.4, 5.7) */}
        <div className="flex items-center gap-2">
          <ProcessingStatusBadge matterId={matterId} />
          <ConsistencyWarningBadge matterId={matterId} size="sm" interactive />
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-1">
          {/* Export dropdown */}
          <ExportDropdown matterId={matterId} />

          {/* Share dialog */}
          <ShareDialog matterId={matterId} />

          {/* Settings dialog (Story 3.1) */}
          <MatterSettingsDialog matterId={matterId} />

          {/* Delete button - only visible to owners */}
          {currentMatter?.role === 'owner' && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setDeleteDialogOpen(true)}
                  aria-label="Delete matter"
                  className="text-muted-foreground hover:text-destructive"
                  data-testid="workspace-delete-button"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Delete matter</p>
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Delete confirmation dialog */}
        <DeleteMatterDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          matterTitle={currentMatter?.title ?? 'this matter'}
          onDelete={handleDeleteMatter}
        />
      </div>
    </header>
  );
}
