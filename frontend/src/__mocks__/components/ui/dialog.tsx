/**
 * Mock for @/components/ui/dialog
 *
 * This mock provides simple div-based implementations of the Dialog components
 * to avoid the infinite loop issue with Radix UI in jsdom.
 */
import * as React from 'react';

interface DialogProps {
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

function Dialog({ children, open }: DialogProps) {
  return open ? <div data-testid="dialog-root">{children}</div> : null;
}

interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  showCloseButton?: boolean;
}

function DialogContent({ children, className, showCloseButton, ...props }: DialogContentProps) {
  return (
    <div role="dialog" className={className} {...props}>
      {children}
    </div>
  );
}

function DialogHeader({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...props}>{children}</div>;
}

function DialogFooter({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...props}>{children}</div>;
}

function DialogTitle({ children, className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={className} {...props}>{children}</h2>;
}

function DialogDescription({ children, className, id, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p id={id} className={className} {...props}>{children}</p>;
}

function DialogTrigger({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function DialogClose({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function DialogPortal({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function DialogOverlay({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...props}>{children}</div>;
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
};
