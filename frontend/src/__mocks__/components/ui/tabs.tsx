/**
 * Mock for @/components/ui/tabs
 *
 * This mock provides simple div-based implementations of the Tabs components
 * to avoid the infinite loop issue with Radix UI in jsdom.
 */
import * as React from 'react';

interface TabsProps {
  children: React.ReactNode;
  className?: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
}

function Tabs({ children, className, value, defaultValue, onValueChange }: TabsProps) {
  const [activeTab, setActiveTab] = React.useState(value ?? defaultValue ?? '');

  React.useEffect(() => {
    if (value !== undefined) {
      setActiveTab(value);
    }
  }, [value]);

  const handleTabChange = (newValue: string) => {
    if (value === undefined) {
      setActiveTab(newValue);
    }
    onValueChange?.(newValue);
  };

  return (
    <div data-testid="tabs-root" className={className} data-value={activeTab}>
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<{ activeTab?: string; onTabChange?: (v: string) => void }>, {
            activeTab,
            onTabChange: handleTabChange,
          });
        }
        return child;
      })}
    </div>
  );
}

interface TabsListProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  activeTab?: string;
  onTabChange?: (value: string) => void;
}

function TabsList({ children, className, activeTab, onTabChange, ...props }: TabsListProps) {
  return (
    <div role="tablist" className={className} {...props}>
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<{ activeTab?: string; onTabChange?: (v: string) => void }>, {
            activeTab,
            onTabChange,
          });
        }
        return child;
      })}
    </div>
  );
}

interface TabsTriggerProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'value'> {
  children: React.ReactNode;
  value: string;
  activeTab?: string;
  onTabChange?: (value: string) => void;
}

function TabsTrigger({ children, className, value, activeTab, onTabChange, ...props }: TabsTriggerProps) {
  return (
    <button
      role="tab"
      className={className}
      data-value={value}
      data-state={activeTab === value ? 'active' : 'inactive'}
      aria-selected={activeTab === value}
      onClick={() => onTabChange?.(value)}
      {...props}
    >
      {children}
    </button>
  );
}

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  value: string;
  activeTab?: string;
}

function TabsContent({ children, className, value, activeTab, ...props }: TabsContentProps) {
  if (activeTab !== value) {
    return null;
  }
  return (
    <div role="tabpanel" className={className} data-value={value} {...props}>
      {children}
    </div>
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
