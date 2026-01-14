'use client';

import { Component, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  children: ReactNode;
  matterId?: string;
}

interface State {
  hasError: boolean;
}

/**
 * Error Boundary for individual MatterCard components.
 *
 * Catches rendering errors in a single card without crashing the entire grid.
 * Displays a fallback UI for the failed card while allowing others to render.
 */
export class MatterCardErrorBoundary extends Component<Props, State> {
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
      console.error('MatterCard Error:', error, errorInfo);
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="flex flex-col items-center justify-center h-full min-h-[200px] gap-3 py-8">
            <div className="rounded-full bg-destructive/10 p-3">
              <AlertTriangle className="size-6 text-destructive" />
            </div>
            <div className="text-center">
              <p className="font-medium text-destructive">Failed to load matter</p>
              <p className="text-sm text-muted-foreground mt-1">
                This card encountered an error
              </p>
            </div>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}
