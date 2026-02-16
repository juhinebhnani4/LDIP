'use client';

import { useState } from 'react';
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  DollarSign,
  Hash,
  Loader2,
  RefreshCw,
  Zap,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useUsageDashboard } from '@/hooks/useUsageDashboard';

// =============================================================================
// Helpers
// =============================================================================

function formatUsd(val: number): string {
  return `$${val.toFixed(2)}`;
}

function formatInr(val: number): string {
  return `₹${val.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

function formatTokens(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
  return String(val);
}

function formatOperationName(op: string): string {
  return op
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatProviderName(provider: string): string {
  const map: Record<string, string> = {
    'gpt-4-turbo-preview': 'GPT-4 Turbo',
    'gpt-4o': 'GPT-4o',
    'gpt-4o-mini': 'GPT-4o Mini',
    'gpt-3.5-turbo': 'GPT-3.5 Turbo',
    'text-embedding-3-small': 'Embeddings (Small)',
    'text-embedding-3-large': 'Embeddings (Large)',
    'gemini-2.5-flash': 'Gemini 2.5 Flash',
    'gemini-1.5-pro': 'Gemini 1.5 Pro',
    'rerank-v3.5': 'Cohere Rerank',
    'document-ai': 'Document AI (OCR)',
  };
  return map[provider] || provider;
}

// Provider colors for chart
const PROVIDER_COLORS: Record<string, string> = {
  'gpt-4-turbo-preview': '#10b981',
  'gpt-4o': '#3b82f6',
  'gpt-4o-mini': '#8b5cf6',
  'gpt-3.5-turbo': '#06b6d4',
  'text-embedding-3-small': '#f59e0b',
  'text-embedding-3-large': '#f97316',
  'gemini-2.5-flash': '#ef4444',
  'gemini-1.5-pro': '#ec4899',
  'rerank-v3.5': '#14b8a6',
  'document-ai': '#6366f1',
};

function getProviderColor(provider: string): string {
  return PROVIDER_COLORS[provider] || '#6b7280';
}

// =============================================================================
// Component
// =============================================================================

export default function UsageDashboardPage() {
  const now = new Date();
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);

  const { data, isLoading, error, refresh } = useUsageDashboard(
    selectedYear,
    selectedMonth,
  );

  // Month navigation
  const goToPreviousMonth = () => {
    if (selectedMonth === 1) {
      setSelectedMonth(12);
      setSelectedYear(selectedYear - 1);
    } else {
      setSelectedMonth(selectedMonth - 1);
    }
  };

  const goToNextMonth = () => {
    const isCurrentMonth =
      selectedYear === now.getFullYear() && selectedMonth === now.getMonth() + 1;
    if (isCurrentMonth) return;
    if (selectedMonth === 12) {
      setSelectedMonth(1);
      setSelectedYear(selectedYear + 1);
    } else {
      setSelectedMonth(selectedMonth + 1);
    }
  };

  const monthLabel = new Date(selectedYear, selectedMonth - 1).toLocaleDateString(
    'en-US',
    { month: 'long', year: 'numeric' },
  );

  const isCurrentMonth =
    selectedYear === now.getFullYear() && selectedMonth === now.getMonth() + 1;

  const budgetPct = data
    ? Math.min((data.totalSpendUsd / data.budgetUsd) * 100, 100)
    : 0;

  const budgetColor =
    budgetPct >= 90
      ? 'bg-red-500'
      : budgetPct >= 70
        ? 'bg-yellow-500'
        : 'bg-green-500';

  return (
    <div className="px-4 sm:px-6 py-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="size-8 text-primary" />
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
                Usage Dashboard
              </h1>
              <p className="text-muted-foreground">
                LLM cost tracking across all providers
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={goToPreviousMonth}
              aria-label="Previous month"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-[150px] text-center text-sm font-medium">
              {monthLabel}
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={goToNextMonth}
              disabled={isCurrentMonth}
              aria-label="Next month"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={refresh}
              disabled={isLoading}
              aria-label="Refresh"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* Loading / Error */}
        {isLoading && !data ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : error && !data ? (
          <Card>
            <CardContent className="py-10 text-center text-destructive">
              {error.message}
            </CardContent>
          </Card>
        ) : data ? (
          <>
            {/* Top Summary Cards */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {/* Total Spend */}
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="flex items-center gap-1">
                    <DollarSign className="h-3.5 w-3.5" />
                    Total Spend
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">{formatUsd(data.totalSpendUsd)}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatInr(data.totalSpendInr)}
                  </p>
                </CardContent>
              </Card>

              {/* Budget */}
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Budget</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">
                    {budgetPct.toFixed(0)}%
                  </p>
                  <Progress
                    value={budgetPct}
                    className="mt-2 h-2"
                    indicatorClassName={budgetColor}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatUsd(data.totalSpendUsd)} / {formatUsd(data.budgetUsd)}
                  </p>
                </CardContent>
              </Card>

              {/* Tokens */}
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5" />
                    Tokens
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">
                    {formatTokens(data.totalTokens)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    total tokens this month
                  </p>
                </CardContent>
              </Card>

              {/* Requests */}
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="flex items-center gap-1">
                    <Hash className="h-3.5 w-3.5" />
                    Requests
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">
                    {data.totalRequests.toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    API calls this month
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Daily Spend Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Daily Spend</CardTitle>
                <CardDescription>Cost per day in USD</CardDescription>
              </CardHeader>
              <CardContent>
                {data.dailySpend.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={data.dailySpend}>
                      <XAxis
                        dataKey="date"
                        tickFormatter={(d: string) => {
                          const day = d.split('-')[2];
                          return day ? String(parseInt(day, 10)) : d;
                        }}
                        tick={{ fontSize: 12 }}
                      />
                      <YAxis
                        tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                        tick={{ fontSize: 12 }}
                        width={60}
                      />
                      <Tooltip
                        formatter={(value: number | undefined) => [formatUsd(value ?? 0), 'Spend']}
                        labelFormatter={(label) => `Date: ${String(label)}`}
                      />
                      <Bar dataKey="spendUsd" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-center text-sm text-muted-foreground py-8">
                    No spend data for this month
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Provider & Operation Breakdown */}
            <div className="grid gap-6 lg:grid-cols-2">
              {/* By Provider */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">By Provider</CardTitle>
                  <CardDescription>Spend breakdown by LLM provider</CardDescription>
                </CardHeader>
                <CardContent>
                  {data.byProvider.length > 0 ? (
                    <div className="space-y-3">
                      {data.byProvider.map((p) => {
                        const pct =
                          data.totalSpendUsd > 0
                            ? (p.spendUsd / data.totalSpendUsd) * 100
                            : 0;
                        return (
                          <div key={p.provider} className="space-y-1">
                            <div className="flex items-center justify-between text-sm">
                              <span className="font-medium truncate">
                                {formatProviderName(p.provider)}
                              </span>
                              <span className="text-muted-foreground">
                                {formatUsd(p.spendUsd)} ({pct.toFixed(1)}%)
                              </span>
                            </div>
                            <Progress
                              value={pct}
                              className="h-2"
                              indicatorClassName="transition-all"
                              indicatorStyle={{
                                backgroundColor: getProviderColor(p.provider),
                              }}
                            />
                            <div className="flex gap-3 text-xs text-muted-foreground">
                              <span>{p.requests} reqs</span>
                              <span>{formatTokens(p.inputTokens + p.outputTokens)} {p.provider === 'rerank-v3.5' ? 'units' : 'tokens'}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-center text-sm text-muted-foreground py-4">
                      No data
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* By Operation */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">By Operation</CardTitle>
                  <CardDescription>Spend breakdown by operation type</CardDescription>
                </CardHeader>
                <CardContent>
                  {data.byOperation.length > 0 ? (
                    <ResponsiveContainer width="100%" height={Math.max(200, data.byOperation.length * 36)}>
                      <BarChart
                        data={data.byOperation.slice(0, 10)}
                        layout="vertical"
                        margin={{ left: 8, right: 8 }}
                      >
                        <XAxis
                          type="number"
                          tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                          tick={{ fontSize: 11 }}
                        />
                        <YAxis
                          type="category"
                          dataKey="operation"
                          tickFormatter={formatOperationName}
                          tick={{ fontSize: 11 }}
                          width={140}
                        />
                        <Tooltip
                          formatter={(value: number | undefined) => [formatUsd(value ?? 0), 'Spend']}
                          labelFormatter={(label) =>
                            formatOperationName(String(label))
                          }
                        />
                        <Bar dataKey="spendUsd" radius={[0, 4, 4, 0]}>
                          {data.byOperation.slice(0, 10).map((entry, idx) => (
                            <Cell
                              key={entry.operation}
                              fill={
                                [
                                  '#3b82f6',
                                  '#10b981',
                                  '#f59e0b',
                                  '#ef4444',
                                  '#8b5cf6',
                                  '#06b6d4',
                                  '#ec4899',
                                  '#f97316',
                                  '#14b8a6',
                                  '#6366f1',
                                ][idx % 10]
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="text-center text-sm text-muted-foreground py-4">
                      No data
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Top Matters */}
            {data.byMatter.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Top Matters by Cost</CardTitle>
                  <CardDescription>
                    Top {data.byMatter.length} matters by spend
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {data.byMatter.map((m) => {
                      const maxSpend = data.byMatter[0]?.spendUsd || 1;
                      const pct = (m.spendUsd / maxSpend) * 100;
                      return (
                        <div key={m.matterId} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-mono text-xs truncate max-w-[200px]">
                              {m.matterId.slice(0, 8)}...
                            </span>
                            <span className="text-muted-foreground">
                              {formatUsd(m.spendUsd)} &middot; {m.requests} reqs
                            </span>
                          </div>
                          <Progress
                            value={pct}
                            className="h-1.5"
                            indicatorClassName="bg-blue-500"
                          />
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
