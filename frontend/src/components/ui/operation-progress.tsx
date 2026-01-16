'use client'

import { Check, Circle, Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

export type OperationStepStatus = 'pending' | 'in-progress' | 'completed' | 'error'

export interface OperationStep {
  /** Unique identifier for the step */
  id: string
  /** Display label for the step */
  label: string
  /** Current status of the step */
  status: OperationStepStatus
  /** Optional error message if status is 'error' */
  errorMessage?: string
}

export interface OperationProgressProps {
  /** List of steps in the operation */
  steps: OperationStep[]
  /** Optional title for the operation */
  title?: string
  /** Additional CSS classes */
  className?: string
}

const statusIcons: Record<OperationStepStatus, React.ReactNode> = {
  pending: <Circle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />,
  'in-progress': <Loader2 className="h-4 w-4 text-primary animate-spin" aria-hidden="true" />,
  completed: <Check className="h-4 w-4 text-green-600" aria-hidden="true" />,
  error: <Circle className="h-4 w-4 text-destructive" aria-hidden="true" />,
}

const statusLabels: Record<OperationStepStatus, string> = {
  pending: 'Pending',
  'in-progress': 'In progress',
  completed: 'Completed',
  error: 'Failed',
}

/**
 * Multi-step operation progress component.
 * Story 13.4: Graceful Degradation and Error States (AC #2)
 *
 * Features:
 * - Visual step indicators
 * - Status icons for each step
 * - Error messages for failed steps
 * - Accessible with appropriate ARIA attributes
 */
export function OperationProgress({ steps, title, className }: OperationProgressProps) {
  const completedSteps = steps.filter((s) => s.status === 'completed').length
  const totalSteps = steps.length

  return (
    <div
      className={cn('space-y-3', className)}
      role="group"
      aria-label={title ?? 'Operation progress'}
    >
      {title && (
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium">{title}</h4>
          <span className="text-xs text-muted-foreground">
            {completedSteps}/{totalSteps} completed
          </span>
        </div>
      )}

      <ul className="space-y-2" role="list">
        {steps.map((step) => (
          <li key={step.id} className="flex items-start gap-3">
            <span className="mt-0.5 shrink-0" aria-hidden="true">
              {statusIcons[step.status]}
            </span>
            <div className="flex-1 min-w-0">
              <p
                className={cn(
                  'text-sm',
                  step.status === 'completed' && 'text-muted-foreground',
                  step.status === 'error' && 'text-destructive'
                )}
              >
                {step.label}
                <span className="sr-only"> - {statusLabels[step.status]}</span>
              </p>
              {step.status === 'error' && step.errorMessage && (
                <p className="text-xs text-destructive mt-0.5">{step.errorMessage}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
