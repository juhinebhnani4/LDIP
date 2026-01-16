'use client';

import { useState, useCallback } from 'react';
import { Download, FileText, FileType, Presentation, Zap, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ExportBuilder } from '@/components/features/export';
import { generateExecutiveSummary } from '@/lib/api/exports';
import { toast } from 'sonner';
import type { ExportFormat } from '@/types/export';

/** Export format configuration */
const EXPORT_FORMATS = [
  {
    value: 'pdf' as ExportFormat,
    label: 'Export as PDF',
    icon: FileText,
    description: 'Download as PDF document',
  },
  {
    value: 'word' as ExportFormat,
    label: 'Export as Word',
    icon: FileType,
    description: 'Download as Word document',
  },
  {
    value: 'powerpoint' as ExportFormat,
    label: 'Export as PowerPoint',
    icon: Presentation,
    description: 'Download as PowerPoint presentation',
  },
] as const;

interface ExportDropdownProps {
  /** Matter ID for export context */
  matterId: string;
}

/**
 * Export Dropdown Component
 *
 * Provides export options for the matter workspace.
 * Opens Export Builder modal for section selection.
 *
 * Story 10A.1: Workspace Shell Header - AC #3
 * Story 12.1: Export Builder Modal with Section Selection
 * Story 12.4: Quick Export - Executive Summary (AC #1)
 *
 * @param matterId - Matter ID for export context
 */
export function ExportDropdown({ matterId }: ExportDropdownProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('pdf');
  const [isGeneratingQuickExport, setIsGeneratingQuickExport] = useState(false);

  const handleExport = (format: ExportFormat) => {
    setSelectedFormat(format);
    setModalOpen(true);
  };

  /**
   * Handle Quick Export: Executive Summary
   *
   * Generates a pre-configured 1-2 page PDF executive summary with one click.
   * Story 12.4: AC #1, #2 - One-click generation without modal.
   *
   * Features:
   * - No configuration required
   * - Opens download URL in new tab on success
   * - Shows toast notifications for success/failure
   *
   * @returns Promise that resolves when generation completes
   */
  const handleQuickExport = useCallback(async (): Promise<void> => {
    setIsGeneratingQuickExport(true);
    try {
      const result = await generateExecutiveSummary(matterId);
      if (result.downloadUrl) {
        window.open(result.downloadUrl, '_blank');
        toast.success('Executive summary downloaded');
      } else {
        toast.error('Failed to generate executive summary - no download URL');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate executive summary';
      toast.error(errorMessage);
    } finally {
      setIsGeneratingQuickExport(false);
    }
  }, [matterId]);

  return (
    <>
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Export options">
                <Download className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent>
            <p>Export</p>
          </TooltipContent>
        </Tooltip>
        <DropdownMenuContent align="end" className="w-56">
          {/* Quick Export Section - Story 12.4: AC #1 */}
          <DropdownMenuItem
            onClick={handleQuickExport}
            disabled={isGeneratingQuickExport}
            className="flex items-center gap-2 cursor-pointer"
          >
            {isGeneratingQuickExport ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4" />
            )}
            <div className="flex flex-col">
              <span>Quick Export: Executive Summary</span>
              <span className="text-xs text-muted-foreground">1-2 page PDF overview</span>
            </div>
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          {/* Full Export Builder Options */}
          {EXPORT_FORMATS.map((format) => {
            const Icon = format.icon;
            return (
              <DropdownMenuItem
                key={format.value}
                onClick={() => handleExport(format.value)}
                className="flex items-center gap-2 cursor-pointer"
              >
                <Icon className="h-4 w-4" />
                <span>{format.label}</span>
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      <ExportBuilder
        matterId={matterId}
        format={selectedFormat}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
