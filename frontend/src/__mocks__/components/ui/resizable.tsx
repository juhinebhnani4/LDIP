/**
 * Mock for @/components/ui/resizable
 *
 * This mock provides simple div-based implementations of the resizable panel components
 * to avoid issues with react-resizable-panels in jsdom.
 */
import * as React from 'react';

interface ResizablePanelGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  direction?: 'horizontal' | 'vertical';
}

function ResizablePanelGroup({ children, className, direction = 'horizontal', ...props }: ResizablePanelGroupProps) {
  return (
    <div
      data-testid="resizable-panel-group"
      data-panel-group-direction={direction}
      className={className}
      style={{ display: 'flex', flexDirection: direction === 'vertical' ? 'column' : 'row' }}
      {...props}
    >
      {children}
    </div>
  );
}

interface ResizablePanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  defaultSize?: number;
  minSize?: number;
  maxSize?: number;
}

function ResizablePanel({ children, className, defaultSize, minSize, maxSize, ...props }: ResizablePanelProps) {
  return (
    <div
      data-testid="resizable-panel"
      className={className}
      style={{ flex: defaultSize ? `${defaultSize} 1 0%` : '1 1 0%' }}
      {...props}
    >
      {children}
    </div>
  );
}

interface ResizableHandleProps extends React.HTMLAttributes<HTMLDivElement> {
  withHandle?: boolean;
}

function ResizableHandle({ className, withHandle, ...props }: ResizableHandleProps) {
  return (
    <div data-testid="resizable-handle" className={className} {...props}>
      {withHandle && <div>⋮</div>}
    </div>
  );
}

export { ResizablePanelGroup, ResizablePanel, ResizableHandle };
