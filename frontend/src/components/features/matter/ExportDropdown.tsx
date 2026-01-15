'use client';

import { Download, FileText, FileType, Presentation } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';

/** Export format types */
type ExportFormat = 'pdf' | 'word' | 'powerpoint';

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
 * Currently shows placeholder toast for Epic 12 (Export Builder).
 *
 * Story 10A.1: Workspace Shell Header - AC #3
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function ExportDropdown({ matterId }: ExportDropdownProps) {
  const handleExport = (format: ExportFormat) => {
    // Future: navigate to `/matters/${matterId}/export?format=${format}`
    toast.info(`Export Builder coming in Epic 12 (${format.toUpperCase()} format selected)`);
  };

  return (
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
  );
}
