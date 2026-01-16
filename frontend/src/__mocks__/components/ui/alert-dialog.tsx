/**
 * Mock for @/components/ui/alert-dialog
 *
 * This mock provides simple div-based implementations of the AlertDialog components
 * to avoid the infinite loop issue with Radix UI in jsdom.
 */
import * as React from 'react';

interface AlertDialogProps {
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

function AlertDialog({ children, open }: AlertDialogProps) {
  return open ? <div data-testid="alert-dialog-root">{children}</div> : null;
}

interface AlertDialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

function AlertDialogContent({ children, className, ...props }: AlertDialogContentProps) {
  return (
    <div role="alertdialog" className={className} {...props}>
      {children}
    </div>
  );
}

function AlertDialogHeader({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...props}>{children}</div>;
}

function AlertDialogFooter({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...props}>{children}</div>;
}

function AlertDialogTitle({ children, className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={className} {...props}>{children}</h2>;
}

function AlertDialogDescription({ children, className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={className} {...props}>{children}</p>;
}

function AlertDialogTrigger({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function AlertDialogAction({ children, onClick, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button onClick={onClick} className={className} {...props}>{children}</button>;
}

function AlertDialogCancel({ children, onClick, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button onClick={onClick} className={className} {...props}>{children}</button>;
}

function AlertDialogPortal({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function AlertDialogOverlay({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...props}>{children}</div>;
}

export {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogTitle,
  AlertDialogTrigger,
};
