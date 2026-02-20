'use client';

/**
 * A/B Testing Dashboard Widget
 *
 * Gap 10: Automated Voyage A/B Testing
 *
 * Displays:
 * - Current traffic routing configuration
 * - Latest comparison results with statistical analysis
 * - Score comparison bars (control vs treatment)
 * - Decision and confidence indicator
 * - Latency comparison
 */

import { useABTesting } from '@/hooks/useABTesting';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { FlaskConical, Loader2, RefreshCw, AlertTriangle, CheckCircle2, XCircle, Minus } from 'lucide-react';
import type { ABTestRun, ABTestScores } from '@/lib/api/ab-testing';

// =============================================================================
// Score Bar Component
// =============================================================================

function ScoreBar({
  label,
  controlValue,
  treatmentValue,
}: {
  label: string;
  controlValue: number | null;
  treatmentValue: number | null;
}) {
  const cv = controlValue ?? 0;
  const tv = treatmentValue ?? 0;
  const controlPct = cv * 100; // Scores are 0-1
  const treatmentPct = tv * 100;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span>
          {cv.toFixed(3)} vs {tv.toFixed(3)}
        </span>
      </div>
      <div className="flex gap-1 h-3">
        {/* Control bar */}
        <div className="flex-1 bg-muted rounded-sm overflow-hidden" title={`Control: ${cv.toFixed(3)}`}>
          <div
            className="h-full bg-blue-500/70 rounded-sm transition-all"
            style={{ width: `${Math.min(controlPct, 100)}%` }}
          />
        </div>
        {/* Treatment bar */}
        <div className="flex-1 bg-muted rounded-sm overflow-hidden" title={`Treatment: ${tv.toFixed(3)}`}>
          <div
            className="h-full bg-amber-500/70 rounded-sm transition-all"
            style={{ width: `${Math.min(treatmentPct, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Decision Badge
// =============================================================================

function DecisionBadge({ decision, confidence }: { decision: string | null; confidence: number | null }) {
  if (!decision) return null;

  const config: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
    treatment_wins: { icon: CheckCircle2, color: 'text-green-500', label: 'Voyage Wins' },
    control_wins: { icon: XCircle, color: 'text-red-500', label: 'OpenAI Wins' },
    no_significant_difference: { icon: Minus, color: 'text-yellow-500', label: 'No Difference' },
    insufficient_data: { icon: AlertTriangle, color: 'text-orange-500', label: 'Need More Data' },
  };

  const c = config[decision] || { icon: AlertTriangle, color: 'text-gray-500', label: decision };
  const Icon = c.icon;
  const confPct = confidence ? `${(confidence * 100).toFixed(0)}%` : '';

  return (
    <div className={`flex items-center gap-1.5 ${c.color}`}>
      <Icon className="size-4" aria-hidden="true" />
      <span className="text-sm font-medium">{c.label}</span>
      {confPct && <span className="text-xs text-muted-foreground">({confPct} conf.)</span>}
    </div>
  );
}

// =============================================================================
// Latest Run Detail
// =============================================================================

function LatestRunDetail({ run }: { run: ABTestRun }) {
  const cs = run.controlScores;
  const ts = run.treatmentScores;

  return (
    <div className="space-y-3">
      {/* Decision */}
      <div className="flex items-center justify-between">
        <DecisionBadge decision={run.decision} confidence={run.decisionConfidence} />
        {run.goldenItemCount != null && run.goldenItemCount > 0 && (
          <span className="text-xs text-muted-foreground">{run.goldenItemCount} items</span>
        )}
      </div>

      {/* Reasoning */}
      {run.decisionReasoning && (
        <p className="text-xs text-muted-foreground leading-relaxed">{run.decisionReasoning}</p>
      )}

      {/* Score bars */}
      {cs && ts && (
        <div className="space-y-2 pt-1">
          <div className="flex justify-between text-[10px] text-muted-foreground uppercase tracking-wider">
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-blue-500/70" /> Control (OpenAI)
            </span>
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-amber-500/70" /> Treatment (Voyage)
            </span>
          </div>
          <ScoreBar label="Overall" controlValue={cs.overall} treatmentValue={ts.overall} />
          <ScoreBar label="Faithfulness" controlValue={cs.faithfulness} treatmentValue={ts.faithfulness} />
          <ScoreBar label="Relevancy" controlValue={cs.answer_relevancy} treatmentValue={ts.answer_relevancy} />
          <ScoreBar label="Recall" controlValue={cs.context_recall} treatmentValue={ts.context_recall} />
        </div>
      )}

      {/* Latency comparison */}
      {(run.controlLatencyP50 != null || run.treatmentLatencyP50 != null) && (
        <div className="flex gap-4 pt-1 text-xs text-muted-foreground">
          <div>
            <span className="font-medium">Latency P50:</span>{' '}
            {run.controlLatencyP50 ?? '–'}ms vs {run.treatmentLatencyP50 ?? '–'}ms
          </div>
          {(run.controlLatencyP95 != null || run.treatmentLatencyP95 != null) && (
            <div>
              <span className="font-medium">P95:</span>{' '}
              {run.controlLatencyP95 ?? '–'}ms vs {run.treatmentLatencyP95 ?? '–'}ms
            </div>
          )}
        </div>
      )}

      {/* Statistical test */}
      {run.statisticalTest && (
        <div className="text-[10px] text-muted-foreground bg-muted/50 rounded px-2 py-1 font-mono">
          p={run.statisticalTest.p_value_approx.toFixed(4)}{' '}
          d={run.statisticalTest.effect_size_cohens_d.toFixed(3)}{' '}
          t={run.statisticalTest.t_statistic.toFixed(2)}{' '}
          df={run.statisticalTest.degrees_of_freedom.toFixed(0)}
        </div>
      )}

      {/* Timestamp */}
      {run.completedAt && run.completedAt.length > 0 && (
        <div className="text-[10px] text-muted-foreground">
          Completed {new Date(run.completedAt).toLocaleString()}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Status Indicator
// =============================================================================

function StatusIndicator({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-400',
    running_control: 'bg-blue-400 animate-pulse',
    running_treatment: 'bg-amber-400 animate-pulse',
    comparing: 'bg-purple-400 animate-pulse',
    completed: 'bg-green-400',
    failed: 'bg-red-400',
  };
  const labels: Record<string, string> = {
    pending: 'Pending',
    running_control: 'Evaluating Control...',
    running_treatment: 'Evaluating Treatment...',
    comparing: 'Comparing...',
    completed: 'Completed',
    failed: 'Failed',
  };

  return (
    <div className="flex items-center gap-1.5 text-xs" role="status">
      <span className={`size-2 rounded-full ${colors[status] || 'bg-gray-400'}`} aria-hidden="true" />
      <span className="text-muted-foreground">{labels[status] || status}</span>
    </div>
  );
}

// =============================================================================
// Main Widget
// =============================================================================

export function ABTestingWidget() {
  const { status, loading, error, refresh } = useABTesting();

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-5 text-primary" />
            <CardTitle className="text-base">A/B Testing</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-6">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-5 text-primary" />
            <div>
              <CardTitle className="text-base">A/B Testing</CardTitle>
              <CardDescription className="text-xs">
                Voyage vs OpenAI provider comparison
              </CardDescription>
            </div>
          </div>
          <button
            onClick={refresh}
            className="p-1 rounded hover:bg-muted transition-colors"
            title="Refresh"
            aria-label="Refresh A/B testing status"
          >
            <RefreshCw className="size-3.5 text-muted-foreground" />
          </button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {error && (
          <div className="text-xs text-red-500 bg-red-50 dark:bg-red-950/20 rounded px-2 py-1">
            {error}
          </div>
        )}

        {status && (
          <>
            {/* Config summary */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-muted/50 rounded px-2 py-1.5">
                <div className="text-muted-foreground">A/B Enabled</div>
                <div className="font-medium">{status.enabled ? 'Yes' : 'No'}</div>
              </div>
              <div className="bg-muted/50 rounded px-2 py-1.5">
                <div className="text-muted-foreground">Voyage Traffic</div>
                <div className="font-medium">{status.trafficPercentage}%</div>
              </div>
              <div className="bg-muted/50 rounded px-2 py-1.5">
                <div className="text-muted-foreground">Auto-Promote</div>
                <div className="font-medium">{status.autoPromoteEnabled ? 'On' : 'Off'}</div>
              </div>
              <div className="bg-muted/50 rounded px-2 py-1.5">
                <div className="text-muted-foreground">Completed Runs</div>
                <div className="font-medium">{status.totalCompletedRuns}</div>
              </div>
            </div>

            {/* Running experiment */}
            {status.running && (
              <div className="border rounded-md px-3 py-2 space-y-1">
                <StatusIndicator status={status.running.status} />
                <div className="text-[10px] text-muted-foreground">
                  {status.running.createdAt && status.running.createdAt.length > 0 &&
                    `Started ${new Date(status.running.createdAt).toLocaleString()}`
                  }
                </div>
              </div>
            )}

            {/* Latest completed run */}
            {status.latestRun && status.latestRun.status === 'completed' && (
              <div className="border rounded-md px-3 py-2.5 space-y-2">
                <div className="text-xs font-medium text-muted-foreground">Latest Comparison</div>
                <LatestRunDetail run={status.latestRun} />
              </div>
            )}

            {/* No runs yet */}
            {!status.latestRun && !status.running && (
              <div className="text-center py-3 text-xs text-muted-foreground">
                No comparison experiments run yet.
                <br />
                Trigger one from the evaluation page.
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
