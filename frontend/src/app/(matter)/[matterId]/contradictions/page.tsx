import { AlertTriangle } from 'lucide-react';

interface ContradictionsPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Contradictions Tab Placeholder Page
 *
 * Will show detected contradictions with severity scoring and explanations.
 *
 * Story 10A.2: Tab Bar Navigation (placeholder)
 * Implementation: Phase 2 (deferred per architecture)
 */
export default async function ContradictionsPage({ params }: ContradictionsPageProps) {
  const { matterId } = await params;

  return (
    <div className="container py-8" id="tabpanel-contradictions" role="tabpanel" aria-labelledby="tab-contradictions">
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <AlertTriangle className="h-16 w-16 text-muted-foreground mb-4" aria-hidden="true" />
        <h1 className="text-2xl font-semibold mb-2">Contradictions</h1>
        <p className="text-muted-foreground max-w-md">
          The Contradictions tab will show detected contradictions with
          severity scoring, type classification, and detailed explanations.
        </p>
        <p className="text-sm text-muted-foreground mt-4">
          Coming in Phase 2
        </p>
        <p className="text-xs text-muted-foreground/70 mt-2">
          Matter ID: {matterId}
        </p>
      </div>
    </div>
  );
}
