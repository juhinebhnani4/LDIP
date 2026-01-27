'use client';

import { useState, useCallback, useEffect } from 'react';
import { Settings, Loader2, Scale, FileCheck, IndianRupee, TrendingUp, RefreshCw, Globe, Briefcase, Lock, Zap, SearchCheck } from 'lucide-react';
import { useMatterCosts } from '@/hooks/useMatterCosts';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import type { VerificationMode, DataResidency, AnalysisMode } from '@/types/matter';
import { DATA_RESIDENCY_OPTIONS, ANALYSIS_MODE_OPTIONS } from '@/types/matter';
import { Input } from '@/components/ui/input';
import { updateMatter } from '@/lib/api/matters';
import { useMatterStore } from '@/stores/matterStore';

/**
 * Verification mode options with descriptions
 * Story 3.1: Configurable verification gates per matter
 */
const VERIFICATION_MODES: {
  value: VerificationMode;
  label: string;
  icon: typeof Scale;
  description: string;
}[] = [
  {
    value: 'advisory',
    label: 'Advisory',
    icon: FileCheck,
    description: 'Default mode. Exports show acknowledgment checkbox but allow download.',
  },
  {
    value: 'required',
    label: 'Court-Ready',
    icon: Scale,
    description: '100% verification required before export. Use for court submissions.',
  },
];

interface MatterSettingsDialogProps {
  /** Matter ID for settings context */
  matterId: string;
}

/**
 * Matter Settings Dialog Component
 *
 * Allows users to configure matter-level settings including verification mode.
 *
 * Story 3.1: Add Verification Mode Setting to Matters
 * - Configurable verification requirements per matter
 * - Default = advisory (acknowledgment only)
 * - Court-ready = 100% verification required
 */
export function MatterSettingsDialog({ matterId }: MatterSettingsDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const currentMatter = useMatterStore((state) => state.currentMatter);
  const updateStoreMatter = useMatterStore((state) => state.updateMatter);

  // Story 7.1: Per-Matter Cost Tracking
  const { data: costData, isLoading: costsLoading, refetch: refetchCosts } = useMatterCosts(matterId);

  // Local state for verification mode
  const [verificationMode, setVerificationMode] = useState<VerificationMode>(
    currentMatter?.verificationMode ?? 'advisory'
  );

  // Story 7.2: Practice group for cost reporting
  const [practiceGroup, setPracticeGroup] = useState<string>(
    currentMatter?.practiceGroup ?? ''
  );

  // Story 6.4: Analysis mode for document processing
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>(
    currentMatter?.analysisMode ?? 'deep_analysis'
  );

  // Code Review Fix: Only sync local state when dialog OPENS, not on every store change
  // This prevents overwriting unsaved user changes if store updates from another source
  useEffect(() => {
    if (isOpen && currentMatter) {
      setVerificationMode(currentMatter.verificationMode ?? 'advisory');
      setPracticeGroup(currentMatter.practiceGroup ?? '');
      setAnalysisMode(currentMatter.analysisMode ?? 'deep_analysis');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]); // Intentionally only depend on isOpen, not currentMatter

  // Check if user can edit settings (owner or editor)
  const canEdit = currentMatter?.role === 'owner' || currentMatter?.role === 'editor';

  const handleSave = useCallback(async () => {
    if (!canEdit) {
      toast.error('You do not have permission to change settings');
      return;
    }

    setIsSaving(true);

    try {
      const updatedMatter = await updateMatter(matterId, {
        verificationMode,
        practiceGroup: practiceGroup || null,
        analysisMode,
      });

      // Update store with new matter data
      updateStoreMatter(updatedMatter);

      toast.success('Settings saved');
      setIsOpen(false);
    } catch {
      toast.error('Failed to save settings. Please try again.');
    } finally {
      setIsSaving(false);
    }
  }, [matterId, verificationMode, practiceGroup, analysisMode, canEdit, updateStoreMatter]);

  // Check if there are unsaved changes
  const hasChanges =
    verificationMode !== (currentMatter?.verificationMode ?? 'advisory') ||
    practiceGroup !== (currentMatter?.practiceGroup ?? '') ||
    analysisMode !== (currentMatter?.analysisMode ?? 'deep_analysis');

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Settings"
              data-testid="workspace-settings-button"
            >
              <Settings className="h-4 w-4" />
            </Button>
          </DialogTrigger>
        </TooltipTrigger>
        <TooltipContent>
          <p>Settings</p>
        </TooltipContent>
      </Tooltip>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Matter Settings</DialogTitle>
          <DialogDescription>
            Configure settings for this matter. Changes will apply immediately.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          {/* Verification Mode Section */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-muted-foreground" />
              <Label htmlFor="verification-mode" className="text-sm font-medium">
                Verification Mode
              </Label>
            </div>
            <Select
              value={verificationMode}
              onValueChange={(value) => setVerificationMode(value as VerificationMode)}
              disabled={!canEdit}
            >
              <SelectTrigger id="verification-mode" className="w-full">
                <SelectValue placeholder="Select mode" />
              </SelectTrigger>
              <SelectContent>
                {VERIFICATION_MODES.map((mode) => {
                  const Icon = mode.icon;
                  return (
                    <SelectItem key={mode.value} value={mode.value}>
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4" />
                        <span>{mode.label}</span>
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
            {/* Description of selected mode */}
            <p className="text-xs text-muted-foreground">
              {VERIFICATION_MODES.find((m) => m.value === verificationMode)?.description}
            </p>
            {!canEdit && (
              <p className="text-xs text-amber-600">
                Only editors and owners can change settings.
              </p>
            )}
          </div>

          <Separator />

          {/* Info about verification mode */}
          <div className="rounded-lg border bg-muted/50 p-3 space-y-2">
            <p className="text-xs font-medium">About Verification Modes</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              <li>
                <strong>Advisory:</strong> Findings can be exported with acknowledgment. Good for
                internal review.
              </li>
              <li>
                <strong>Court-Ready:</strong> All findings must be verified before export. Required
                for court submissions.
              </li>
            </ul>
          </div>

          <Separator />

          {/* Story 6.4: Analysis Mode Section */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <Label htmlFor="analysis-mode" className="text-sm font-medium">
                Analysis Mode
              </Label>
            </div>
            <Select
              value={analysisMode}
              onValueChange={(value) => setAnalysisMode(value as AnalysisMode)}
              disabled={!canEdit}
            >
              <SelectTrigger id="analysis-mode" className="w-full">
                <SelectValue placeholder="Select mode" />
              </SelectTrigger>
              <SelectContent>
                {ANALYSIS_MODE_OPTIONS.map((mode) => (
                  <SelectItem key={mode.value} value={mode.value}>
                    <div className="flex items-center gap-2">
                      {mode.value === 'deep_analysis' ? (
                        <SearchCheck className="h-4 w-4" />
                      ) : (
                        <Zap className="h-4 w-4" />
                      )}
                      <span>{mode.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {ANALYSIS_MODE_OPTIONS.find((m) => m.value === analysisMode)?.description}
            </p>
            {analysisMode === 'quick_scan' && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950 p-2">
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  Quick Scan is ~40% faster and ~30% cheaper but skips contradiction detection.
                </p>
              </div>
            )}
          </div>

          <Separator />

          {/* Story 7.1: Cost Tracking Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IndianRupee className="h-4 w-4 text-muted-foreground" />
                <Label className="text-sm font-medium">Cost Tracking (30 days)</Label>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => refetchCosts()}
                disabled={costsLoading}
                aria-label="Refresh costs"
              >
                <RefreshCw className={`h-3 w-3 ${costsLoading ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            {costsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : costData ? (
              <div className="space-y-3">
                {/* Total Cost */}
                <div className="rounded-lg border bg-muted/50 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Total Cost</span>
                    <span className="text-lg font-semibold">
                      ₹{costData.totalCostInr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    ${costData.totalCostUsd.toFixed(2)} USD
                  </p>
                </div>

                {/* Weekly Cost */}
                <div className="flex items-center gap-2 text-sm">
                  <TrendingUp className="h-4 w-4 text-blue-500" />
                  <span className="text-muted-foreground">This week:</span>
                  <span className="font-medium">
                    ₹{costData.weeklyCostInr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                  </span>
                </div>

                {/* Cost by Operation */}
                {costData.byOperation.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">By Operation</p>
                    <div className="space-y-1">
                      {costData.byOperation.slice(0, 4).map((op) => (
                        <div
                          key={op.operation}
                          className="flex items-center justify-between text-xs"
                        >
                          <span className="text-muted-foreground">{op.operation}</span>
                          <span>₹{op.costInr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Operations Count */}
                <p className="text-xs text-muted-foreground text-center pt-1">
                  {costData.operationCount.toLocaleString()} LLM operations
                </p>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">
                No cost data available
              </p>
            )}
          </div>

          <Separator />

          {/* Story 7.2: Practice Group for Cost Reporting */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-muted-foreground" />
              <Label htmlFor="practice-group" className="text-sm font-medium">
                Practice Group
              </Label>
            </div>
            <Input
              id="practice-group"
              placeholder="e.g., Litigation, Corporate, IP"
              value={practiceGroup}
              onChange={(e) => setPracticeGroup(e.target.value)}
              disabled={!canEdit}
              maxLength={100}
            />
            <p className="text-xs text-muted-foreground">
              Used for cost reporting and analytics. Optional.
            </p>
          </div>

          <Separator />

          {/* Story 7.3: Data Residency Display (Read-only) */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-muted-foreground" />
              <Label className="text-sm font-medium">
                Data Residency
              </Label>
              <Lock className="h-3 w-3 text-muted-foreground" />
            </div>
            <div className="rounded-lg border bg-muted/50 p-3">
              <p className="text-sm font-medium">
                {DATA_RESIDENCY_OPTIONS.find(
                  (opt) => opt.value === (currentMatter?.dataResidency ?? 'default')
                )?.label ?? 'Auto'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {DATA_RESIDENCY_OPTIONS.find(
                  (opt) => opt.value === (currentMatter?.dataResidency ?? 'default')
                )?.description}
              </p>
            </div>
            <p className="text-xs text-amber-600">
              Data residency cannot be changed after documents are uploaded.
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setIsOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || !hasChanges || !canEdit}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
