'use client';

import { useEffect, useState } from 'react';
import { Loader2, TrendingDown, TrendingUp } from 'lucide-react';
import { api } from '@/lib/api/client';

interface ProviderCostStats {
  totalInr: number;
  totalUsd: number;
  queryCount: number;
  avgCostPerQueryInr: number;
}

interface CostComparisonData {
  embedding: {
    openai?: ProviderCostStats;
    voyage?: ProviderCostStats;
  };
  reranking: {
    cohere?: ProviderCostStats;
    voyage?: ProviderCostStats;
  };
  savings: {
    embeddingInr: number;
    rerankingInr: number;
    totalInr: number;
  };
  periodDays: number;
}

interface CostComparisonDashboardProps {
  matterId?: string;
  days?: number;
}

function StatCard({
  title,
  providerA,
  providerB,
  labelA,
  labelB,
  savings,
}: {
  title: string;
  providerA?: ProviderCostStats;
  providerB?: ProviderCostStats;
  labelA: string;
  labelB: string;
  savings: number;
}) {
  const hasSavings = savings > 0;

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold text-card-foreground">{title}</h3>

      <div className="grid grid-cols-2 gap-4">
        {/* Provider A */}
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">{labelA}</p>
          <p className="text-lg font-bold tabular-nums">
            {providerA ? `₹${providerA.totalInr.toFixed(2)}` : '—'}
          </p>
          <p className="text-xs text-muted-foreground">
            {providerA ? `${providerA.queryCount} queries` : 'No data'}
          </p>
          {providerA && providerA.queryCount > 0 && (
            <p className="text-xs text-muted-foreground">
              ₹{providerA.avgCostPerQueryInr.toFixed(4)}/query
            </p>
          )}
        </div>

        {/* Provider B */}
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">{labelB}</p>
          <p className="text-lg font-bold tabular-nums">
            {providerB ? `₹${providerB.totalInr.toFixed(2)}` : '—'}
          </p>
          <p className="text-xs text-muted-foreground">
            {providerB ? `${providerB.queryCount} queries` : 'No data'}
          </p>
          {providerB && providerB.queryCount > 0 && (
            <p className="text-xs text-muted-foreground">
              ₹{providerB.avgCostPerQueryInr.toFixed(4)}/query
            </p>
          )}
        </div>
      </div>

      {/* Savings */}
      {(providerA?.queryCount ?? 0) > 0 && (providerB?.queryCount ?? 0) > 0 && (
        <div className={`mt-3 flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${
          hasSavings
            ? 'bg-green-50 text-green-700 dark:bg-green-950/50 dark:text-green-300'
            : 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300'
        }`}>
          {hasSavings ? (
            <TrendingDown className="h-3 w-3" />
          ) : (
            <TrendingUp className="h-3 w-3" />
          )}
          <span>
            {hasSavings
              ? `Voyage saved ₹${savings.toFixed(2)}`
              : `Voyage cost ₹${Math.abs(savings).toFixed(2)} more`
            }
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * CostComparisonDashboard - Side-by-side provider cost comparison.
 *
 * Shows OpenAI vs Voyage embeddings and Cohere vs Voyage reranking costs
 * with savings calculations for A/B testing analysis.
 */
export function CostComparisonDashboard({ matterId, days = 30 }: CostComparisonDashboardProps) {
  const [data, setData] = useState<CostComparisonData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setIsLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ days: String(days) });
        if (matterId) params.set('matter_id', matterId);

        const response = await api.get<{ data: CostComparisonData }>(
          `/api/costs/comparison?${params}`,
        );
        setData(response.data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load cost data');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [matterId, days]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Provider Cost Comparison</h2>
        <span className="text-xs text-muted-foreground">Last {data.periodDays} days</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <StatCard
          title="Embedding Costs"
          providerA={data.embedding.openai ?? undefined}
          providerB={data.embedding.voyage ?? undefined}
          labelA="OpenAI Small"
          labelB="Voyage Law-2"
          savings={data.savings.embeddingInr}
        />
        <StatCard
          title="Reranking Costs"
          providerA={data.reranking.cohere ?? undefined}
          providerB={data.reranking.voyage ?? undefined}
          labelA="Cohere v3.5"
          labelB="Voyage 2.5"
          savings={data.savings.rerankingInr}
        />
      </div>

      {/* Total savings banner */}
      {data.savings.totalInr !== 0 && (
        <div className={`rounded-lg px-4 py-3 text-sm font-medium ${
          data.savings.totalInr > 0
            ? 'bg-green-50 text-green-800 dark:bg-green-950/50 dark:text-green-200'
            : 'bg-amber-50 text-amber-800 dark:bg-amber-950/50 dark:text-amber-200'
        }`}>
          {data.savings.totalInr > 0
            ? `Total savings with Voyage: ₹${data.savings.totalInr.toFixed(2)} over ${data.periodDays} days`
            : `Voyage costs ₹${Math.abs(data.savings.totalInr).toFixed(2)} more over ${data.periodDays} days`
          }
        </div>
      )}
    </div>
  );
}
