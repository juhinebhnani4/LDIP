import type { ReactNode } from 'react';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="min-h-screen">
      {/* Dashboard header will be implemented in Epic 9 */}
      <main className="container mx-auto py-6">{children}</main>
    </div>
  );
}
