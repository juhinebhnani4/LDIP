'use client';

/**
 * PDF Error Boundary Component
 *
 * Catches errors from PDF.js rendering and provides a graceful fallback UI.
 *
 * Story 3-4: Split-View Citation Highlighting
 */

import { Component, type ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface PdfErrorBoundaryProps {
  children: ReactNode;
  /** Fallback message to display */
  fallbackMessage?: string;
  /** Callback when retry is clicked */
  onRetry?: () => void;
}

interface PdfErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary for PDF viewer components.
 *
 * Catches errors during PDF loading/rendering and displays a user-friendly
 * error message with retry option.
 *
 * @example
 * ```tsx
 * <PdfErrorBoundary onRetry={() => refetch()}>
 *   <PdfViewerPanel documentUrl={url} />
 * </PdfErrorBoundary>
 * ```
 */
export class PdfErrorBoundary extends Component<
  PdfErrorBoundaryProps,
  PdfErrorBoundaryState
> {
  constructor(props: PdfErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): PdfErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to error reporting service in production
    console.error('PDF Error Boundary caught error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onRetry?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full bg-muted/30 p-8">
          <AlertCircle className="h-12 w-12 text-destructive mb-4" />
          <h3 className="text-lg font-medium mb-2">
            Failed to load PDF
          </h3>
          <p className="text-sm text-muted-foreground text-center mb-4 max-w-md">
            {this.props.fallbackMessage ||
              'There was an error loading the PDF document. This may be due to a network issue or corrupted file.'}
          </p>
          {this.state.error && (
            <p className="text-xs text-muted-foreground mb-4 font-mono">
              {this.state.error.message}
            </p>
          )}
          <Button onClick={this.handleRetry} variant="outline" className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Try Again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
