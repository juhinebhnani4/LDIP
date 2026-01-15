import { Skeleton } from '@/components/ui/skeleton';

/**
 * Loading State for Upload Page
 *
 * Displays a skeleton while the upload wizard loads.
 */
export default function UploadLoading() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header skeleton */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <Skeleton className="h-5 w-40" />
        </div>
      </header>

      {/* Main content skeleton */}
      <main className="container mx-auto px-4 py-8 max-w-2xl">
        <Skeleton className="h-8 w-48 mx-auto mb-8" />

        {/* Drop zone skeleton */}
        <div className="border-2 border-dashed border-muted rounded-lg p-16">
          <div className="flex flex-col items-center gap-4">
            <Skeleton className="h-24 w-24 rounded-full" />
            <Skeleton className="h-6 w-64" />
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-4 w-56" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
      </main>
    </div>
  );
}
