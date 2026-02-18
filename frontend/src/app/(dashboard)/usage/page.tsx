'use client';

import {
  BarChart3,
  FileText,
  FolderOpen,
  Loader2,
  MessageSquare,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useUsageSummary } from '@/hooks/useUsageSummary';

export default function UsagePage() {
  const { data, isLoading, error, refresh } = useUsageSummary();

  return (
    <div className="px-4 sm:px-6 py-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="size-8 text-primary" />
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
                Usage
              </h1>
              <p className="text-muted-foreground">
                Your activity across all matters
              </p>
            </div>
          </div>
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

        {/* Loading */}
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
            {/* Summary Cards */}
            <div className="grid gap-4 sm:grid-cols-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="flex items-center gap-1">
                    <FileText className="h-3.5 w-3.5" />
                    Documents
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">
                    {data.totalDocuments.toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    across {data.totalMatters} matter{data.totalMatters !== 1 ? 's' : ''}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="flex items-center gap-1">
                    <FolderOpen className="h-3.5 w-3.5" />
                    Pages Processed
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">
                    {data.totalPages.toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    total pages analyzed
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardDescription className="flex items-center gap-1">
                    <MessageSquare className="h-3.5 w-3.5" />
                    Queries
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">
                    {data.totalQueries.toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    questions asked
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Per-Matter Breakdown */}
            {data.matters.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">By Matter</CardTitle>
                  <CardDescription>
                    Usage breakdown per matter
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* Table header */}
                    <div className="grid grid-cols-[1fr_80px_80px_80px] gap-2 text-xs font-medium text-muted-foreground border-b pb-2">
                      <span>Matter</span>
                      <span className="text-right">Docs</span>
                      <span className="text-right">Pages</span>
                      <span className="text-right">Queries</span>
                    </div>
                    {data.matters.map((m) => {
                      const maxPages = data.matters[0]?.pages || 1;
                      const pct = maxPages > 0 ? (m.pages / maxPages) * 100 : 0;
                      return (
                        <div key={m.matterId} className="space-y-1">
                          <div className="grid grid-cols-[1fr_80px_80px_80px] gap-2 text-sm items-center">
                            <span className="font-medium truncate" title={m.matterTitle}>
                              {m.matterTitle}
                            </span>
                            <span className="text-right text-muted-foreground">
                              {m.documents}
                            </span>
                            <span className="text-right text-muted-foreground">
                              {m.pages.toLocaleString()}
                            </span>
                            <span className="text-right text-muted-foreground">
                              {m.queries}
                            </span>
                          </div>
                          <Progress
                            value={pct}
                            className="h-1"
                            indicatorClassName="bg-primary/60"
                          />
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {data.matters.length === 0 && (
              <Card>
                <CardContent className="py-10 text-center text-muted-foreground">
                  No matters yet. Create a matter and upload documents to see usage.
                </CardContent>
              </Card>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
