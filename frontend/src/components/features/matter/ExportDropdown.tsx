'use client';

import { useState } from 'react';
import { Download, FileText, FileType, Presentation } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ExportBuilder } from '@/components/features/export';
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
 *
 * @param matterId - Matter ID for export context
 */
export function ExportDropdown({ matterId }: ExportDropdownProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('pdf');

  const handleExport = (format: ExportFormat) => {
    setSelectedFormat(format);
    setModalOpen(true);
  };

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
        <DropdownMenuContent align="end" className="w-48">
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
