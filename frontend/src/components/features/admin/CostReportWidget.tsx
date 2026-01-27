'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  IndianRupee,
  Loader2,
  RefreshCw,
  FileText,
  Building2,
  ChevronLeft,
  ChevronRight,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from 'sonner';
import {
  getMonthlyCostReport,
  type MonthlyCostReport,
} from '@/lib/api/admin-quota';

/**
 * Cost Report Widget for Admin Dashboard
 *
 * Story 7.2: Monthly Cost Report by Practice Group
 *
 * Displays:
 * - Total cost across all practice groups
 * - Breakdown by practice group with matter/document counts
 * - Month navigation
 * - CSV export functionality
 */
export function CostReportWidget() {
  const [report, setReport] = useState<MonthlyCostReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Current month/year for navigation
  const now = new Date();
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);

  const fetchReport = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getMonthlyCostReport(selectedYear, selectedMonth);
      setReport(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load cost report';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedYear, selectedMonth]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

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
    const now = new Date();
    const isCurrentMonth =
      selectedYear === now.getFullYear() && selectedMonth === now.getMonth() + 1;

    if (isCurrentMonth) return; // Don't go beyond current month

    if (selectedMonth === 12) {
      setSelectedMonth(1);
      setSelectedYear(selectedYear + 1);
    } else {
      setSelectedMonth(selectedMonth + 1);
    }
  };

  // Format month for display
  const monthLabel = new Date(selectedYear, selectedMonth - 1).toLocaleDateString('en-IN', {
    month: 'long',
    year: 'numeric',
  });

  // Check if at current month
  const isCurrentMonth =
    selectedYear === now.getFullYear() && selectedMonth === now.getMonth() + 1;

  // Export to CSV
  const handleExportCSV = () => {
    if (!report) return;

    const headers = ['Practice Group', 'Matters', 'Documents', 'Cost (INR)', 'Cost (USD)'];
    const rows = report.practiceGroups.map((pg) => [
      pg.practiceGroup,
      pg.matterCount.toString(),
      pg.documentCount.toString(),
      pg.totalCostInr.toFixed(2),
      pg.totalCostUsd.toFixed(2),
    ]);

    // Add totals row
    rows.push([
      'TOTAL',
      report.practiceGroups.reduce((sum, pg) => sum + pg.matterCount, 0).toString(),
      report.practiceGroups.reduce((sum, pg) => sum + pg.documentCount, 0).toString(),
      report.totalCostInr.toFixed(2),
      report.totalCostUsd.toFixed(2),
    ]);

    const csv = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `cost-report-${report.reportMonth}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast.success('Report exported to CSV');
  };

  return (
    <Card className="col-span-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IndianRupee className="h-5 w-5 text-primary" />
            <div>
              <CardTitle className="text-lg">Cost Report</CardTitle>
              <CardDescription>Monthly cost breakdown by practice group</CardDescription>
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
            <span className="min-w-[140px] text-center text-sm font-medium">
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
              onClick={fetchReport}
              disabled={isLoading}
              aria-label="Refresh"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCSV}
              disabled={!report || isLoading}
              className="gap-1"
            >
              <Download className="h-4 w-4" />
              CSV
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-destructive">{error}</div>
        ) : report ? (
          <div className="space-y-4">
            {/* Total Summary */}
            <div className="flex items-center justify-between rounded-lg border bg-muted/50 p-4">
              <div className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  {report.practiceGroups.length} practice groups
                </span>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold">
                  ₹{report.totalCostInr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </p>
                <p className="text-xs text-muted-foreground">
                  ${report.totalCostUsd.toFixed(2)} USD
                </p>
              </div>
            </div>

            {/* Practice Group Table */}
            {report.practiceGroups.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Practice Group</TableHead>
                    <TableHead className="text-right">Matters</TableHead>
                    <TableHead className="text-right">Documents</TableHead>
                    <TableHead className="text-right">Cost (INR)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.practiceGroups.map((pg) => (
                    <TableRow key={pg.practiceGroup}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          {pg.practiceGroup}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">{pg.matterCount}</TableCell>
                      <TableCell className="text-right">{pg.documentCount}</TableCell>
                      <TableCell className="text-right font-medium">
                        ₹{pg.totalCostInr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-center text-sm text-muted-foreground py-4">
                No cost data for this period
              </p>
            )}

            {/* Generated timestamp */}
            <p className="text-xs text-muted-foreground text-right">
              Generated: {new Date(report.generatedAt).toLocaleString()}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
