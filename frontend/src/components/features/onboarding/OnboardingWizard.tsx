'use client';

/**
 * OnboardingWizard Component
 *
 * 10-step onboarding wizard for new users with database persistence.
 * Expands on the FeatureTour pattern with enhanced features:
 * - Phase-based organization (Getting Started, Exploring Results, Taking Action)
 * - Database persistence via user preferences
 * - Skip with confirmation
 * - Restart capability from Help menu
 *
 * Story 6.2: Onboarding Wizard
 * Task 6.2.4: Create OnboardingWizard.tsx component
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { X, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import { useUserPreferences, type OnboardingStage } from '@/hooks/useUserPreferences';

const ONBOARDING_LOCAL_KEY = 'ldip-onboarding-in-progress';

/**
 * Onboarding wizard steps organized by phase.
 */
interface WizardStep {
  id: OnboardingStage;
  target: string;
  title: string;
  content: string;
  phase: 'Getting Started' | 'Exploring Results' | 'Taking Action';
  placement?: 'top' | 'bottom' | 'left' | 'right';
}

const wizardSteps: WizardStep[] = [
  // Phase 1: Getting Started
  {
    id: 'dashboard',
    target: '[data-tour="matter-list"]',
    title: 'Your Matters',
    content: 'Your matters appear here. Each matter is a case or project with its own documents and findings.',
    phase: 'Getting Started',
    placement: 'bottom',
  },
  {
    id: 'upload',
    target: '[data-tour="upload-button"]',
    title: 'Upload Documents',
    content: 'Upload documents to start. We support PDF, DOCX, and images. Processing starts automatically.',
    phase: 'Getting Started',
    placement: 'left',
  },
  {
    id: 'settings',
    target: '[data-tour="matter-settings"]',
    title: 'Matter Settings',
    content: 'Configure verification requirements and analysis depth here. Choose between advisory and court-ready modes.',
    phase: 'Getting Started',
    placement: 'bottom',
  },
  // Phase 2: Exploring Results
  {
    id: 'summary',
    target: '[data-tour="summary-tab"]',
    title: 'Summary Tab',
    content: 'AI-generated overview of your case with key findings, parties, and main themes identified.',
    phase: 'Exploring Results',
    placement: 'bottom',
  },
  {
    id: 'timeline',
    target: '[data-tour="timeline-tab"]',
    title: 'Timeline Tab',
    content: 'Events extracted chronologically from your documents. See the story unfold in order.',
    phase: 'Exploring Results',
    placement: 'bottom',
  },
  {
    id: 'entities',
    target: '[data-tour="entities-tab"]',
    title: 'Entities Tab',
    content: 'People, organizations, and locations identified in your case. See how they connect.',
    phase: 'Exploring Results',
    placement: 'bottom',
  },
  {
    id: 'contradictions',
    target: '[data-tour="contradictions-tab"]',
    title: 'Contradictions Tab',
    content: 'Conflicting statements flagged for your review. Critical for deposition preparation.',
    phase: 'Exploring Results',
    placement: 'bottom',
  },
  {
    id: 'citations',
    target: '[data-tour="citations-tab"]',
    title: 'Citations Tab',
    content: 'Key passages with direct links to source documents. Click to view the original text.',
    phase: 'Exploring Results',
    placement: 'bottom',
  },
  // Phase 3: Taking Action
  {
    id: 'qa',
    target: '[data-tour="qa-panel"]',
    title: 'Q&A Chat',
    content: 'Ask questions in natural language. AI searches your documents and provides cited answers.',
    phase: 'Taking Action',
    placement: 'left',
  },
  {
    id: 'verification',
    target: '[data-tour="verification-tab"]',
    title: 'Verification & Export',
    content: 'Review AI findings before export. Required for court-ready mode. Approve, reject, or flag items.',
    phase: 'Taking Action',
    placement: 'bottom',
  },
];

interface OnboardingWizardProps {
  /** Force show the wizard regardless of completion status */
  forceShow?: boolean;
  /** Callback when wizard completes or is dismissed */
  onComplete?: () => void;
}

export function OnboardingWizard({ forceShow = false, onComplete }: OnboardingWizardProps) {
  const { preferences, updatePreferences, isLoading: prefsLoading } = useUserPreferences();

  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [showSkipConfirm, setShowSkipConfirm] = useState(false);

  // Determine if wizard should show
  useEffect(() => {
    if (prefsLoading) return;

    if (forceShow) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Opening wizard on forceShow is intentional
      setIsOpen(true);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Resetting step on forceShow is intentional
      setCurrentStep(0);
      return;
    }

    // Don't show if already completed
    if (preferences?.onboardingCompleted) {
      return;
    }

    // Check localStorage for in-progress state
    const localProgress = localStorage.getItem(ONBOARDING_LOCAL_KEY);
    if (localProgress) {
      const parsed = JSON.parse(localProgress);
      if (parsed.inProgress) {
        // Resume from saved step
        const savedStepIndex = wizardSteps.findIndex((s) => s.id === parsed.stage);
        setCurrentStep(savedStepIndex >= 0 ? savedStepIndex : 0);
        setIsOpen(true);
      }
    }
  }, [forceShow, preferences?.onboardingCompleted, prefsLoading]);

  // Update target rect when step changes
  useEffect(() => {
    if (!isOpen) return;

    const step = wizardSteps[currentStep];
    if (!step) return;

    const updateTargetRect = () => {
      const element = document.querySelector(step.target);
      if (element) {
        setTargetRect(element.getBoundingClientRect());
      } else {
        setTargetRect(null);
      }
    };

    updateTargetRect();
    window.addEventListener('resize', updateTargetRect);
    window.addEventListener('scroll', updateTargetRect);

    // Save progress to localStorage
    localStorage.setItem(
      ONBOARDING_LOCAL_KEY,
      JSON.stringify({ inProgress: true, stage: step.id })
    );

    return () => {
      window.removeEventListener('resize', updateTargetRect);
      window.removeEventListener('scroll', updateTargetRect);
    };
  }, [isOpen, currentStep]);

  const finishWizard = useCallback(async () => {
    // Mark completed in database
    try {
      await updatePreferences({
        onboardingCompleted: true,
        onboardingStage: null,
      });
    } catch {
      // Continue even if API fails - localStorage is backup
    }

    // Clear localStorage
    localStorage.removeItem(ONBOARDING_LOCAL_KEY);

    setIsOpen(false);
    onComplete?.();
  }, [updatePreferences, onComplete]);

  const handleNext = useCallback(async () => {
    if (currentStep < wizardSteps.length - 1) {
      const nextStep = wizardSteps[currentStep + 1];
      setCurrentStep((prev) => prev + 1);

      // Persist stage to database
      try {
        await updatePreferences({ onboardingStage: nextStep?.id ?? null });
      } catch {
        // Continue - localStorage is backup
      }
    } else {
      await finishWizard();
    }
  }, [currentStep, updatePreferences, finishWizard]);

  const handlePrev = useCallback(async () => {
    if (currentStep > 0) {
      const prevStep = wizardSteps[currentStep - 1];
      setCurrentStep((prev) => prev - 1);

      // Persist stage to database
      try {
        await updatePreferences({ onboardingStage: prevStep?.id ?? null });
      } catch {
        // Continue - localStorage is backup
      }
    }
  }, [currentStep, updatePreferences]);

  const handleSkip = useCallback(() => {
    setShowSkipConfirm(true);
  }, []);

  const confirmSkip = useCallback(async () => {
    setShowSkipConfirm(false);

    // Mark as NOT completed but clear in-progress state
    try {
      await updatePreferences({
        onboardingCompleted: false,
        onboardingStage: null,
      });
    } catch {
      // Continue
    }

    localStorage.removeItem(ONBOARDING_LOCAL_KEY);
    setIsOpen(false);
    onComplete?.();
  }, [updatePreferences, onComplete]);

  // Progress calculation
  const progressPercent = useMemo(
    () => Math.round(((currentStep + 1) / wizardSteps.length) * 100),
    [currentStep]
  );

  if (!isOpen) return null;

  const step = wizardSteps[currentStep];
  const isLastStep = currentStep === wizardSteps.length - 1;
  const isFirstStep = currentStep === 0;

  const tooltipPosition = getTooltipPosition(
    targetRect,
    step?.placement ?? 'bottom'
  );

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 z-[100] bg-black/50" onClick={handleSkip} />

      {/* Spotlight on target element */}
      {targetRect && (
        <div
          className="fixed z-[101] rounded-lg ring-4 ring-primary ring-offset-4 ring-offset-background pointer-events-none"
          style={{
            top: targetRect.top - 4,
            left: targetRect.left - 4,
            width: targetRect.width + 8,
            height: targetRect.height + 8,
          }}
        />
      )}

      {/* Tooltip */}
      <div
        className={cn(
          'fixed z-[102] w-96 bg-background border rounded-lg shadow-lg p-5',
          !targetRect && 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'
        )}
        style={targetRect ? tooltipPosition : undefined}
      >
        <button
          onClick={handleSkip}
          className="absolute top-3 right-3 text-muted-foreground hover:text-foreground"
          aria-label="Skip tour"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Phase indicator */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-medium text-primary bg-primary/10 px-2 py-0.5 rounded">
            {step?.phase}
          </span>
        </div>

        <h3 className="font-semibold text-lg mb-2">{step?.title}</h3>
        <p className="text-sm text-muted-foreground mb-4">{step?.content}</p>

        {/* Progress bar */}
        <div className="space-y-2 mb-4">
          <Progress value={progressPercent} className="h-1.5" />
          <p className="text-xs text-muted-foreground text-center">
            Step {currentStep + 1} of {wizardSteps.length}
          </p>
        </div>

        <div className="flex items-center justify-between">
          <Button variant="outline" size="sm" onClick={handlePrev} disabled={isFirstStep}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
          <Button size="sm" onClick={handleNext}>
            {isLastStep ? (
              'Finish'
            ) : (
              <>
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </>
            )}
          </Button>
        </div>

        <p className="text-xs text-muted-foreground mt-3 text-center">
          <button onClick={handleSkip} className="hover:underline">
            Skip for now
          </button>
        </p>
      </div>

      {/* Skip confirmation dialog */}
      <AlertDialog open={showSkipConfirm} onOpenChange={setShowSkipConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Skip Onboarding?
            </AlertDialogTitle>
            <AlertDialogDescription>
              You can restart the tour anytime from the Help menu. Would you like to skip for now?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Continue Tour</AlertDialogCancel>
            <AlertDialogAction onClick={confirmSkip}>Skip for Now</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function getTooltipPosition(
  rect: DOMRect | null,
  placement: 'top' | 'bottom' | 'left' | 'right'
): React.CSSProperties {
  if (!rect) {
    return {};
  }

  const offset = 16;
  const tooltipWidth = 384; // w-96 = 24rem = 384px
  const tooltipHeight = 260;

  switch (placement) {
    case 'top':
      return {
        top: Math.max(8, rect.top - tooltipHeight - offset),
        left: Math.max(8, Math.min(rect.left + rect.width / 2 - tooltipWidth / 2, window.innerWidth - tooltipWidth - 8)),
      };
    case 'bottom':
      return {
        top: Math.min(rect.bottom + offset, window.innerHeight - tooltipHeight - 8),
        left: Math.max(8, Math.min(rect.left + rect.width / 2 - tooltipWidth / 2, window.innerWidth - tooltipWidth - 8)),
      };
    case 'left':
      return {
        top: Math.max(8, Math.min(rect.top + rect.height / 2 - tooltipHeight / 2, window.innerHeight - tooltipHeight - 8)),
        left: Math.max(8, rect.left - tooltipWidth - offset),
      };
    case 'right':
      return {
        top: Math.max(8, Math.min(rect.top + rect.height / 2 - tooltipHeight / 2, window.innerHeight - tooltipHeight - 8)),
        left: Math.min(rect.right + offset, window.innerWidth - tooltipWidth - 8),
      };
    default:
      return {};
  }
}

/**
 * Hook to trigger the onboarding wizard.
 * Call startOnboarding() to show the wizard.
 */
export function useOnboardingTrigger() {
  const { updatePreferences } = useUserPreferences();

  const startOnboarding = useCallback(async () => {
    // Set in-progress state
    localStorage.setItem(
      ONBOARDING_LOCAL_KEY,
      JSON.stringify({ inProgress: true, stage: 'dashboard' })
    );

    // Reset completion in database
    try {
      await updatePreferences({
        onboardingCompleted: false,
        onboardingStage: 'dashboard',
      });
    } catch {
      // Continue with localStorage backup
    }

    // Force page reload to trigger wizard
    window.location.reload();
  }, [updatePreferences]);

  const resetOnboarding = useCallback(async () => {
    localStorage.removeItem(ONBOARDING_LOCAL_KEY);

    try {
      await updatePreferences({
        onboardingCompleted: false,
        onboardingStage: null,
      });
    } catch {
      // Continue
    }
  }, [updatePreferences]);

  return { startOnboarding, resetOnboarding };
}
