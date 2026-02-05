'use client';

import { useState } from 'react';
import { Trash2, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { adminMaintenanceApi } from '@/lib/api/admin-maintenance';

/**
 * Cleanup Widget Component
 *
 * Admin widget for triggering cleanup of soft-deleted data.
 * Features:
 * - Button to immediately hard-delete all soft-deleted matters
 * - Button to immediately hard-delete all soft-deleted documents
 * - Status feedback showing task triggered state
 *
 * Warning: These actions are irreversible!
 */

interface CleanupWidgetProps {
  /** Optional className for styling */
  className?: string;
}

type CleanupStatus = 'idle' | 'loading' | 'success' | 'error';

interface CleanupState {
  matters: { status: CleanupStatus; message: string | null };
  documents: { status: CleanupStatus; message: string | null };
}

export function CleanupWidget({ className }: CleanupWidgetProps) {
  const [state, setState] = useState<CleanupState>({
    matters: { status: 'idle', message: null },
    documents: { status: 'idle', message: null },
  });

  const handleCleanupMatters = async () => {
    setState((prev) => ({
      ...prev,
      matters: { status: 'loading', message: null },
    }));

    try {
      const response = await adminMaintenanceApi.cleanupDeletedMatters({ retentionDays: 0 });
      setState((prev) => ({
        ...prev,
        matters: {
          status: response.success ? 'success' : 'error',
          message: response.message,
        },
      }));

      // Reset status after 5 seconds
      setTimeout(() => {
        setState((prev) => ({
          ...prev,
          matters: { status: 'idle', message: null },
        }));
      }, 5000);
    } catch (error) {
      setState((prev) => ({
        ...prev,
        matters: {
          status: 'error',
          message: error instanceof Error ? error.message : 'Failed to trigger cleanup',
        },
      }));
    }
  };

  const handleCleanupDocuments = async () => {
    setState((prev) => ({
      ...prev,
      documents: { status: 'loading', message: null },
    }));

    try {
      const response = await adminMaintenanceApi.cleanupDeletedDocuments({ retentionDays: 0 });
      setState((prev) => ({
        ...prev,
        documents: {
          status: response.success ? 'success' : 'error',
          message: response.message,
        },
      }));

      // Reset status after 5 seconds
      setTimeout(() => {
        setState((prev) => ({
          ...prev,
          documents: { status: 'idle', message: null },
        }));
      }, 5000);
    } catch (error) {
      setState((prev) => ({
        ...prev,
        documents: {
          status: 'error',
          message: error instanceof Error ? error.message : 'Failed to trigger cleanup',
        },
      }));
    }
  };

  const getStatusBadge = (status: CleanupStatus) => {
    switch (status) {
      case 'loading':
        return (
          <Badge variant="secondary" className="gap-1">
            <Loader2 className="size-3 animate-spin" />
            Running...
          </Badge>
        );
      case 'success':
        return (
          <Badge variant="default" className="gap-1 bg-green-600">
            <CheckCircle2 className="size-3" />
            Triggered
          </Badge>
        );
      case 'error':
        return (
          <Badge variant="destructive" className="gap-1">
            <AlertTriangle className="size-3" />
            Failed
          </Badge>
        );
      default:
        return null;
    }
  };

  return (
    <Card className={cn('', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Trash2 className="size-5 text-destructive" />
          <CardTitle className="text-lg">Data Cleanup</CardTitle>
        </div>
        <CardDescription>
          Permanently delete soft-deleted data. These actions are irreversible!
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Cleanup Matters */}
        <div className="flex items-center justify-between gap-4 p-3 rounded-lg bg-muted/50">
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm">Deleted Matters</div>
            <div className="text-xs text-muted-foreground truncate">
              {state.matters.message || 'Remove all soft-deleted matters and their data'}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getStatusBadge(state.matters.status)}
            <Button
              variant="destructive"
              size="sm"
              onClick={handleCleanupMatters}
              disabled={state.matters.status === 'loading'}
            >
              {state.matters.status === 'loading' ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                'Cleanup Now'
              )}
            </Button>
          </div>
        </div>

        {/* Cleanup Documents */}
        <div className="flex items-center justify-between gap-4 p-3 rounded-lg bg-muted/50">
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm">Deleted Documents</div>
            <div className="text-xs text-muted-foreground truncate">
              {state.documents.message || 'Remove all soft-deleted documents and storage files'}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getStatusBadge(state.documents.status)}
            <Button
              variant="destructive"
              size="sm"
              onClick={handleCleanupDocuments}
              disabled={state.documents.status === 'loading'}
            >
              {state.documents.status === 'loading' ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                'Cleanup Now'
              )}
            </Button>
          </div>
        </div>

        {/* Info footer */}
        <div className="text-xs text-muted-foreground pt-2 border-t">
          Normally runs automatically at 3:30 AM daily (30-day retention).
          Use these buttons for immediate cleanup.
        </div>
      </CardContent>
    </Card>
  );
}
