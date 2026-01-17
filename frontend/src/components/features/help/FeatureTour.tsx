'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const TOUR_STORAGE_KEY = 'ldip-feature-tour-completed';

interface TourStep {
  target: string;
  title: string;
  content: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
}

const tourSteps: TourStep[] = [
  {
    target: '[data-tour="matter-cards"]',
    title: 'Your Matters',
    content:
      'Your legal matters appear here. Click a card to open the workspace and start analyzing documents.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="upload-button"]',
    title: 'Upload Documents',
    content:
      'Upload case documents here. We support PDF, Word documents, and images. Processing happens automatically.',
    placement: 'left',
  },
  {
    target: '[data-tour="chat-panel"]',
    title: 'Ask Questions',
    content:
      'Ask questions about your documents using natural language. Get answers with citations to the source.',
    placement: 'left',
  },
  {
    target: '[data-tour="timeline-tab"]',
    title: 'Timeline View',
    content:
      'View extracted events on an interactive timeline. See the chronology of your case at a glance.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="help-button"]',
    title: 'Get Help',
    content:
      'Need help? Click here or press ? anytime to access the help center with guides and tips.',
    placement: 'bottom',
  },
];

interface FeatureTourProps {
  forceShow?: boolean;
  onComplete?: () => void;
}

export function FeatureTour({ forceShow = false, onComplete }: FeatureTourProps) {
  // Initialize isOpen based on forceShow or localStorage check
  const [isOpen, setIsOpen] = useState(() => {
    if (forceShow) return true;
    if (typeof window !== 'undefined') {
      const hasCompletedTour = localStorage.getItem(TOUR_STORAGE_KEY);
      return hasCompletedTour ? false : false; // Will be set by timer
    }
    return false;
  });
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);

  // Handle delayed opening for first-time users
  useEffect(() => {
    if (forceShow) return; // forceShow case is handled in initial state

    const hasCompletedTour = localStorage.getItem(TOUR_STORAGE_KEY);
    if (!hasCompletedTour) {
      const timer = setTimeout(() => {
        setIsOpen(true);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [forceShow]);

  useEffect(() => {
    if (!isOpen) return;

    const step = tourSteps[currentStep];
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

    return () => {
      window.removeEventListener('resize', updateTargetRect);
      window.removeEventListener('scroll', updateTargetRect);
    };
  }, [isOpen, currentStep]);

  const finishTour = useCallback(() => {
    localStorage.setItem(TOUR_STORAGE_KEY, 'true');
    setIsOpen(false);
    onComplete?.();
  }, [onComplete]);

  const handleNext = useCallback(() => {
    if (currentStep < tourSteps.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      finishTour();
    }
  }, [currentStep, finishTour]);

  const handlePrev = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  }, [currentStep]);

  const handleSkip = useCallback(() => {
    finishTour();
  }, [finishTour]);

  if (!isOpen) return null;

  const step = tourSteps[currentStep];
  const isLastStep = currentStep === tourSteps.length - 1;
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
          'fixed z-[102] w-80 bg-background border rounded-lg shadow-lg p-4',
          !targetRect && 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'
        )}
        style={targetRect ? tooltipPosition : undefined}
      >
        <button
          onClick={handleSkip}
          className="absolute top-2 right-2 text-muted-foreground hover:text-foreground"
          aria-label="Skip tour"
        >
          <X className="h-4 w-4" />
        </button>

        <h3 className="font-semibold text-lg mb-2">{step?.title}</h3>
        <p className="text-sm text-muted-foreground mb-4">{step?.content}</p>

        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {tourSteps.map((_, index) => (
              <div
                key={index}
                className={cn(
                  'w-2 h-2 rounded-full transition-colors',
                  index === currentStep
                    ? 'bg-primary'
                    : 'bg-muted-foreground/30'
                )}
              />
            ))}
          </div>

          <div className="flex gap-2">
            {!isFirstStep && (
              <Button variant="outline" size="sm" onClick={handlePrev}>
                <ChevronLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
            )}
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
        </div>

        <p className="text-xs text-muted-foreground mt-3 text-center">
          Step {currentStep + 1} of {tourSteps.length}
          {' • '}
          <button onClick={handleSkip} className="hover:underline">
            Skip tour
          </button>
        </p>
      </div>
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
  const tooltipWidth = 320;
  const tooltipHeight = 200;

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

export function useTourReset() {
  return useCallback(() => {
    localStorage.removeItem(TOUR_STORAGE_KEY);
  }, []);
}
