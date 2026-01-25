'use client';

/**
 * ExportTemplateSelector Component
 *
 * Allows users to select from pre-defined export templates for different use cases:
 * - Standard Report: Balanced format for most purposes
 * - Court Filing: Formal format with numbered paragraphs, exhibits, signature block
 * - Internal Memo: Quick summary with bullet points and action items
 *
 * Lawyer UX Improvement: Court-Ready Export Templates
 */

import { Check, FileText, Gavel, FileEdit } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { ExportTemplateId, ExportTemplate } from '@/types/export';
import { EXPORT_TEMPLATES } from '@/types/export';

export interface ExportTemplateSelectorProps {
  /** Currently selected template */
  selectedTemplate: ExportTemplateId;
  /** Callback when template is selected */
  onSelectTemplate: (templateId: ExportTemplateId) => void;
  /** Optional CSS class */
  className?: string;
}

/** Icon mapping for templates */
const TEMPLATE_ICONS = {
  standard: FileText,
  'court-filing': Gavel,
  'internal-memo': FileEdit,
} as const;

/**
 * ExportTemplateSelector - Card-based template selection.
 *
 * @example
 * ```tsx
 * <ExportTemplateSelector
 *   selectedTemplate="court-filing"
 *   onSelectTemplate={(id) => setTemplate(id)}
 * />
 * ```
 */
export function ExportTemplateSelector({
  selectedTemplate,
  onSelectTemplate,
  className,
}: ExportTemplateSelectorProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <div className="text-sm font-medium text-muted-foreground">
        Choose a template
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {EXPORT_TEMPLATES.map((template) => {
          const isSelected = selectedTemplate === template.id;
          const Icon = TEMPLATE_ICONS[template.id];

          return (
            <Card
              key={template.id}
              className={cn(
                'cursor-pointer transition-all hover:border-primary/50',
                isSelected && 'border-primary ring-2 ring-primary/20'
              )}
              onClick={() => onSelectTemplate(template.id)}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        'p-2 rounded-lg',
                        isSelected
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <h4 className="font-medium text-sm">{template.name}</h4>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {template.description}
                      </p>
                    </div>
                  </div>
                  {isSelected && (
                    <Check className="h-4 w-4 text-primary flex-shrink-0" />
                  )}
                </div>

                {/* Key formatting features */}
                <div className="flex flex-wrap gap-1 mt-3">
                  {template.formatting.numberedParagraphs && (
                    <Badge variant="secondary" className="text-[10px] h-5">
                      Numbered
                    </Badge>
                  )}
                  {template.formatting.exhibitLabels && (
                    <Badge variant="secondary" className="text-[10px] h-5">
                      Exhibits
                    </Badge>
                  )}
                  {template.formatting.signatureBlock && (
                    <Badge variant="secondary" className="text-[10px] h-5">
                      Signature
                    </Badge>
                  )}
                  {template.formatting.bulletPoints && (
                    <Badge variant="secondary" className="text-[10px] h-5">
                      Bullets
                    </Badge>
                  )}
                  {template.formatting.actionItems && (
                    <Badge variant="secondary" className="text-[10px] h-5">
                      Actions
                    </Badge>
                  )}
                  {template.formatting.tableOfContents && (
                    <Badge variant="secondary" className="text-[10px] h-5">
                      TOC
                    </Badge>
                  )}
                </div>

                {/* Use case hint */}
                <p className="text-[10px] text-muted-foreground mt-2 italic">
                  {template.useCase}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Get template formatting summary for display.
 */
export function getTemplateFormattingSummary(template: ExportTemplate): string {
  const features: string[] = [];

  if (template.formatting.numberedParagraphs) features.push('numbered paragraphs');
  if (template.formatting.tableOfContents) features.push('table of contents');
  if (template.formatting.formalHeaders) features.push('formal headers');
  if (template.formatting.exhibitLabels) features.push('exhibit labels');
  if (template.formatting.signatureBlock) features.push('signature block');
  if (template.formatting.bulletPoints) features.push('bullet points');
  if (template.formatting.actionItems) features.push('action items');

  return features.join(', ');
}
