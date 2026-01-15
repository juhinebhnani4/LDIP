'use client';

import { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
  /** Component name for error logging */
  componentName?: string;
}

interface State {
  hasError: boolean;
}

/**
 * Error Boundary for sidebar components (ActivityFeed, QuickStats).
 *
 * Catches rendering errors in sidebar components without crashing the entire dashboard.
 * Displays a fallback UI with retry option.
 */
export class SidebarErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log error to monitoring service in production
    // For now, just log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error(`Sidebar Error (${this.props.componentName ?? 'unknown'}):`, error, errorInfo);
    }
  }

  handleRetry = (): void => {
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="flex flex-col items-center justify-center py-8 gap-3">
            <div className="rounded-full bg-destructive/10 p-3">
              <AlertTriangle className="size-5 text-destructive" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-destructive">
                Failed to load {this.props.componentName ?? 'component'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Something went wrong
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={this.handleRetry}
              className="mt-2"
            >
              <RefreshCw className="size-4 mr-1" />
              Try again
            </Button>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}
