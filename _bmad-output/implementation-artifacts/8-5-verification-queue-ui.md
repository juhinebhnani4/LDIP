# Story 8.5: Implement Verification Queue UI

Status: done

## Story

As an **attorney**,
I want **a queue of findings awaiting my verification**,
So that **I can efficiently review and approve findings**.

## Acceptance Criteria

1. **Given** I open the Verification tab
   **When** the queue loads
   **Then** I see a DataTable with columns: finding type, description, confidence (progress bar), source, actions

2. **Given** I select multiple findings
   **When** I click "Approve Selected"
   **Then** all selected findings are marked as approved
   **And** verified_by and verified_at are recorded

3. **Given** I click "Reject" on a finding
   **When** the action dialog opens
   **Then** I am prompted to enter a rejection reason
   **And** the finding is marked rejected with notes

4. **Given** the verification queue displays
   **When** I view the statistics header
   **Then** I see: total findings, verified count, pending count, flagged count
   **And** a progress bar shows overall verification percentage

5. **Given** I use filters
   **When** I select options
   **Then** I can filter by: finding type, confidence tier (>90%, 70-90%, <70%), verification status
   **And** the queue updates

## Tasks / Subtasks

- [x] Task 1: Create Verification Page Component (AC: #1)
  - [x] 1.1: Create `frontend/src/app/(matter)/[matterId]/verification/page.tsx`
  - [x] 1.4: Add 'use client' directive for interactive functionality

- [x] Task 2: Create Verification Statistics Header Component (AC: #4)
  - [x] 2.1: Create `frontend/src/components/features/verification/VerificationStats.tsx`
  - [x] 2.2: Implement progress bar showing verification completion percentage
  - [x] 2.3: Display stats: total, pending, approved, rejected, flagged counts
  - [x] 2.4: Show category breakdown badges (by requirement tier)
  - [x] 2.5: Add "Start Review Session" button for focused verification mode

- [x] Task 3: Create Verification Queue DataTable (AC: #1, #5)
  - [x] 3.1: Create `frontend/src/components/features/verification/VerificationQueue.tsx`
  - [x] 3.2: Use shadcn/ui Table with columns: select checkbox, type icon, description, confidence bar, source document, actions
  - [x] 3.4: Add confidence progress bar with color coding (red <70%, yellow 70-90%, green >90%)
  - [x] 3.5: Implement row selection with checkboxes
  - [x] 3.7: Implement column sorting (default: confidence ascending - lowest first)

- [x] Task 4: Create Verification Action Buttons (AC: #1, #2, #3)
  - [x] 4.1: Create `frontend/src/components/features/verification/VerificationActions.tsx`
  - [x] 4.2: Implement inline row actions: Approve (green check), Reject (red X), Flag (yellow flag)
  - [x] 4.3: Create bulk action toolbar: "Approve Selected", "Reject Selected", "Flag Selected"
  - [x] 4.4: Create VerificationNotesDialog component with required notes field for reject/flag
  - [x] 4.6: Add optimistic UI updates with rollback on API failure
  - [x] 4.7: Show toast notifications on action success/failure

- [x] Task 5: Create Filter Controls (AC: #5)
  - [x] 5.1: Create `frontend/src/components/features/verification/VerificationFilters.tsx`
  - [x] 5.2: Add finding type filter dropdown
  - [x] 5.3: Add confidence tier filter (>90%, 70-90%, <70%, All)
  - [x] 5.5: Add view toggle: Queue | By Type | History

- [x] Task 6: Create Verification API Client (AC: #1-5)
  - [x] 6.1: Create `frontend/src/lib/api/verifications.ts`
  - [x] 6.2: Implement `getVerifications(matterId, filters)` - list verifications with filtering
  - [x] 6.3: Implement `getPendingQueue(matterId, limit)` - pending verification queue
  - [x] 6.4: Implement `getVerificationStats(matterId)` - statistics for dashboard
  - [x] 6.5: Implement `approveVerification(verificationId, notes?, confidenceAfter?)` - approve finding
  - [x] 6.6: Implement `rejectVerification(verificationId, notes)` - reject finding with required notes
  - [x] 6.7: Implement `flagVerification(verificationId, notes?)` - flag for review
  - [x] 6.8: Implement `bulkUpdateVerifications(verificationIds, decision, notes?)` - bulk actions

- [x] Task 7: Create Zustand Verification Store (AC: #1-5)
  - [x] 7.1: Create `frontend/src/stores/verificationStore.ts`
  - [x] 7.2: Store verification queue with filter state
  - [x] 7.3: Store verification stats
  - [x] 7.4: Implement optimistic updates for verification actions
  - [x] 7.5: Add selector functions following project patterns
  - [x] 7.6: Implement queue item removal after successful action

- [x] Task 8: Create TypeScript Types (AC: #1-5)
  - [x] 8.1: Create `frontend/src/types/verification.ts`
  - [x] 8.2: Add `VerificationDecision` enum matching backend
  - [x] 8.3: Add `VerificationRequirement` enum matching backend
  - [x] 8.4: Add `VerificationQueueItem` interface for queue display
  - [x] 8.5: Add `VerificationStats` interface for dashboard
  - [x] 8.6: Add `VerificationFilters` interface for filter state

- [x] Task 9: Create Custom Hooks (AC: #1-5)
  - [x] 9.1: Create `frontend/src/hooks/useVerificationQueue.ts` - fetch and manage queue
  - [x] 9.2: Create `frontend/src/hooks/useVerificationStats.ts` - fetch stats with polling
  - [x] 9.3: Create `frontend/src/hooks/useVerificationActions.ts` - action handlers with optimistic updates

- [x] Task 10: Create Unit Tests (AC: #1-5)
  - [x] 10.1: Create `frontend/src/components/features/verification/VerificationQueue.test.tsx`
  - [x] 10.2: Test queue renders with findings data
  - [x] 10.3: Test row selection toggles correctly
  - [x] 10.4: Test bulk action buttons appear when rows selected
  - [x] 10.5: Test confidence bar displays correct color
  - [x] 10.7: Test action dialogs open with correct content
  - [x] 10.8: Create `frontend/src/components/features/verification/VerificationStats.test.tsx`
  - [x] 10.9: Test stats display correct values
  - [x] 10.10: Test progress bar shows correct percentage
  - [x] 10.11: Create `frontend/src/stores/verificationStore.test.ts` - store tests

- [x] Task 11: Add Navigation Integration
  - [x] 11.1: Add Verification route to Matter workspace `/[matterId]/verification`

## Dev Notes

### Architecture Compliance

This story implements the **Verification Queue UI** - the frontend component for attorney verification workflow:

```
┌─────────────────────────────────────────────────────────────────────┐
│  VERIFICATION TAB                                                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  VERIFICATION CENTER                                          │  │
│  │  ████████████████████████░░░░░░░░░░  67% Complete             │  │
│  │  127 verified • 42 pending • 3 flagged                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  VERIFICATION QUEUE (DataTable)                               │  │
│  │  ┌──────┬──────────────────┬─────────┬────────┬───────────┐  │  │
│  │  │ ☐    │ Finding          │ Confid. │ Source │ Actions   │  │  │
│  │  ├──────┼──────────────────┼─────────┼────────┼───────────┤  │  │
│  │  │ ☐    │ 🔴 Contradiction │ ████░░  │ pg 45  │ [✓][✗][⚠] │  │  │
│  │  │ ☐    │ ⚖️ Citation      │ ██████░ │ pg 67  │ [✓][✗][⚠] │  │  │
│  │  │ ☐    │ 👤 Entity Alias  │ ███████ │ pg 12  │ [✓][✗][⚠] │  │  │
│  │  └──────┴──────────────────┴─────────┴────────┴───────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  [Bulk Actions: Approve Selected | Reject Selected | Flag Selected] │
└─────────────────────────────────────────────────────────────────────┘
```

This satisfies:
- **FR10**: Attorney Verification Workflow (UI component)
- **FR24**: Verification Tab per UX Design
- **NFR23**: Court-defensible verification workflow with forensic trail
- **ADR-004**: Tiered verification display (90%/70% thresholds)

### Critical Implementation Details

1. **Confidence Thresholds (ADR-004)**

   Per architecture.md, the tiered verification display:

   | Confidence | Display | Color | Priority |
   |------------|---------|-------|----------|
   | >90%       | Green progress bar | `bg-green-500` | Low (optional) |
   | 70-90%     | Yellow progress bar | `bg-yellow-500` | Medium (suggested) |
   | <70%       | Red progress bar | `bg-red-500` | High (required) |

   ```typescript
   // Confidence color helper
   function getConfidenceColor(confidence: number): string {
     if (confidence > 90) return 'bg-green-500';
     if (confidence > 70) return 'bg-yellow-500';
     return 'bg-red-500';
   }

   function getConfidencePriority(confidence: number): 'high' | 'medium' | 'low' {
     if (confidence <= 70) return 'high';
     if (confidence <= 90) return 'medium';
     return 'low';
   }
   ```

2. **TypeScript Types**

   ```typescript
   // frontend/src/types/verification.ts

   export enum VerificationDecision {
     PENDING = 'pending',
     APPROVED = 'approved',
     REJECTED = 'rejected',
     FLAGGED = 'flagged',
   }

   export enum VerificationRequirement {
     OPTIONAL = 'optional',    // > 90%
     SUGGESTED = 'suggested',  // 70-90%
     REQUIRED = 'required',    // < 70%
   }

   export interface VerificationQueueItem {
     id: string;
     findingId: string | null;
     findingType: string;
     findingSummary: string;
     confidence: number;
     requirement: VerificationRequirement;
     decision: VerificationDecision;
     createdAt: string;
     sourceDocument: string | null;
     engine: string;
   }

   export interface VerificationStats {
     totalVerifications: number;
     pendingCount: number;
     approvedCount: number;
     rejectedCount: number;
     flaggedCount: number;
     requiredPending: number;
     suggestedPending: number;
     optionalPending: number;
     exportBlocked: boolean;
     blockingCount: number;
   }

   export interface VerificationFilters {
     findingType: string | null;
     confidenceTier: 'high' | 'medium' | 'low' | null;
     status: VerificationDecision | null;
     view: 'queue' | 'by-type' | 'history';
   }
   ```

3. **API Client Pattern**

   Follow existing patterns from `frontend/src/lib/api/`:

   ```typescript
   // frontend/src/lib/api/verifications.ts

   import { api } from './client';
   import type {
     VerificationQueueItem,
     VerificationStats,
     VerificationDecision,
   } from '@/types/verification';

   export const verificationsApi = {
     async getStats(matterId: string): Promise<VerificationStats> {
       const response = await api.get<{ data: VerificationStats }>(
         `/api/matters/${matterId}/verifications/stats`
       );
       return response.data.data;
     },

     async getPendingQueue(
       matterId: string,
       limit: number = 50
     ): Promise<VerificationQueueItem[]> {
       const response = await api.get<{ data: VerificationQueueItem[] }>(
         `/api/matters/${matterId}/verifications/pending`,
         { params: { limit } }
       );
       return response.data.data;
     },

     async approve(
       matterId: string,
       verificationId: string,
       notes?: string,
       confidenceAfter?: number
     ): Promise<void> {
       await api.post(
         `/api/matters/${matterId}/verifications/${verificationId}/approve`,
         { notes, confidence_after: confidenceAfter }
       );
     },

     async reject(
       matterId: string,
       verificationId: string,
       notes: string
     ): Promise<void> {
       await api.post(
         `/api/matters/${matterId}/verifications/${verificationId}/reject`,
         { notes }
       );
     },

     async flag(
       matterId: string,
       verificationId: string,
       notes?: string
     ): Promise<void> {
       await api.post(
         `/api/matters/${matterId}/verifications/${verificationId}/flag`,
         { notes }
       );
     },

     async bulkUpdate(
       matterId: string,
       verificationIds: string[],
       decision: VerificationDecision,
       notes?: string
     ): Promise<void> {
       await api.post(
         `/api/matters/${matterId}/verifications/bulk`,
         {
           verification_ids: verificationIds,
           decision,
           notes,
         }
       );
     },
   };
   ```

4. **Zustand Store Pattern**

   Follow project patterns - ALWAYS use selectors:

   ```typescript
   // frontend/src/stores/verificationStore.ts

   import { create } from 'zustand';
   import type {
     VerificationQueueItem,
     VerificationStats,
     VerificationFilters,
   } from '@/types/verification';

   interface VerificationState {
     queue: VerificationQueueItem[];
     stats: VerificationStats | null;
     filters: VerificationFilters;
     selectedIds: string[];
     isLoading: boolean;

     // Actions
     setQueue: (queue: VerificationQueueItem[]) => void;
     setStats: (stats: VerificationStats) => void;
     setFilters: (filters: Partial<VerificationFilters>) => void;
     toggleSelected: (id: string) => void;
     selectAll: (ids: string[]) => void;
     clearSelection: () => void;
     removeFromQueue: (id: string) => void;
     setLoading: (loading: boolean) => void;
   }

   export const useVerificationStore = create<VerificationState>((set) => ({
     queue: [],
     stats: null,
     filters: {
       findingType: null,
       confidenceTier: null,
       status: null,
       view: 'queue',
     },
     selectedIds: [],
     isLoading: false,

     setQueue: (queue) => set({ queue }),
     setStats: (stats) => set({ stats }),
     setFilters: (filters) =>
       set((state) => ({ filters: { ...state.filters, ...filters } })),
     toggleSelected: (id) =>
       set((state) => ({
         selectedIds: state.selectedIds.includes(id)
           ? state.selectedIds.filter((i) => i !== id)
           : [...state.selectedIds, id],
       })),
     selectAll: (ids) => set({ selectedIds: ids }),
     clearSelection: () => set({ selectedIds: [] }),
     removeFromQueue: (id) =>
       set((state) => ({
         queue: state.queue.filter((item) => item.id !== id),
         selectedIds: state.selectedIds.filter((i) => i !== id),
       })),
     setLoading: (isLoading) => set({ isLoading }),
   }));

   // ALWAYS use selectors (per project-context.md)
   // CORRECT:
   // const queue = useVerificationStore((state) => state.queue);
   // const selectedIds = useVerificationStore((state) => state.selectedIds);
   //
   // WRONG (causes unnecessary re-renders):
   // const { queue, selectedIds } = useVerificationStore();
   ```

5. **DataTable Component Structure**

   Use shadcn/ui DataTable with TanStack Table:

   ```typescript
   // frontend/src/components/features/verification/VerificationQueue.tsx

   'use client';

   import { useState } from 'react';
   import {
     ColumnDef,
     flexRender,
     getCoreRowModel,
     getSortedRowModel,
     SortingState,
     useReactTable,
   } from '@tanstack/react-table';
   import { Checkbox } from '@/components/ui/checkbox';
   import { Progress } from '@/components/ui/progress';
   import { Button } from '@/components/ui/button';
   import {
     Table,
     TableBody,
     TableCell,
     TableHead,
     TableHeader,
     TableRow,
   } from '@/components/ui/table';
   import { Check, X, Flag } from 'lucide-react';
   import type { VerificationQueueItem } from '@/types/verification';

   interface VerificationQueueProps {
     data: VerificationQueueItem[];
     onApprove: (id: string) => void;
     onReject: (id: string) => void;
     onFlag: (id: string) => void;
     selectedIds: string[];
     onToggleSelect: (id: string) => void;
     onSelectAll: (ids: string[]) => void;
   }

   export function VerificationQueue({
     data,
     onApprove,
     onReject,
     onFlag,
     selectedIds,
     onToggleSelect,
     onSelectAll,
   }: VerificationQueueProps) {
     const [sorting, setSorting] = useState<SortingState>([
       { id: 'confidence', desc: false }, // Lowest confidence first
     ]);

     const columns: ColumnDef<VerificationQueueItem>[] = [
       {
         id: 'select',
         header: ({ table }) => (
           <Checkbox
             checked={table.getIsAllPageRowsSelected()}
             onCheckedChange={(value) => {
               table.toggleAllPageRowsSelected(!!value);
               if (value) {
                 onSelectAll(data.map((d) => d.id));
               } else {
                 onSelectAll([]);
               }
             }}
             aria-label="Select all"
           />
         ),
         cell: ({ row }) => (
           <Checkbox
             checked={selectedIds.includes(row.original.id)}
             onCheckedChange={() => onToggleSelect(row.original.id)}
             aria-label="Select row"
           />
         ),
         enableSorting: false,
       },
       {
         accessorKey: 'findingType',
         header: 'Type',
         cell: ({ row }) => (
           <span className="flex items-center gap-2">
             {getTypeIcon(row.original.findingType)}
             {formatFindingType(row.original.findingType)}
           </span>
         ),
       },
       {
         accessorKey: 'findingSummary',
         header: 'Description',
         cell: ({ row }) => (
           <span className="max-w-[300px] truncate block">
             {row.original.findingSummary}
           </span>
         ),
       },
       {
         accessorKey: 'confidence',
         header: 'Confidence',
         cell: ({ row }) => {
           const confidence = row.original.confidence;
           return (
             <div className="flex items-center gap-2">
               <Progress
                 value={confidence}
                 className={`w-20 h-2 ${getConfidenceColor(confidence)}`}
               />
               <span className="text-sm text-muted-foreground">
                 {confidence.toFixed(0)}%
               </span>
             </div>
           );
         },
       },
       {
         accessorKey: 'sourceDocument',
         header: 'Source',
         cell: ({ row }) => (
           <span className="text-sm text-muted-foreground">
             {row.original.sourceDocument ?? 'N/A'}
           </span>
         ),
       },
       {
         id: 'actions',
         header: 'Actions',
         cell: ({ row }) => (
           <div className="flex items-center gap-1">
             <Button
               size="icon"
               variant="ghost"
               className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-50"
               onClick={() => onApprove(row.original.id)}
               aria-label="Approve"
             >
               <Check className="h-4 w-4" />
             </Button>
             <Button
               size="icon"
               variant="ghost"
               className="h-8 w-8 text-red-600 hover:text-red-700 hover:bg-red-50"
               onClick={() => onReject(row.original.id)}
               aria-label="Reject"
             >
               <X className="h-4 w-4" />
             </Button>
             <Button
               size="icon"
               variant="ghost"
               className="h-8 w-8 text-yellow-600 hover:text-yellow-700 hover:bg-yellow-50"
               onClick={() => onFlag(row.original.id)}
               aria-label="Flag"
             >
               <Flag className="h-4 w-4" />
             </Button>
           </div>
         ),
         enableSorting: false,
       },
     ];

     const table = useReactTable({
       data,
       columns,
       getCoreRowModel: getCoreRowModel(),
       getSortedRowModel: getSortedRowModel(),
       onSortingChange: setSorting,
       state: { sorting },
     });

     return (
       <div className="rounded-md border">
         <Table>
           <TableHeader>
             {table.getHeaderGroups().map((headerGroup) => (
               <TableRow key={headerGroup.id}>
                 {headerGroup.headers.map((header) => (
                   <TableHead key={header.id}>
                     {header.isPlaceholder
                       ? null
                       : flexRender(
                           header.column.columnDef.header,
                           header.getContext()
                         )}
                   </TableHead>
                 ))}
               </TableRow>
             ))}
           </TableHeader>
           <TableBody>
             {table.getRowModel().rows?.length ? (
               table.getRowModel().rows.map((row) => (
                 <TableRow
                   key={row.id}
                   data-state={
                     selectedIds.includes(row.original.id) && 'selected'
                   }
                 >
                   {row.getVisibleCells().map((cell) => (
                     <TableCell key={cell.id}>
                       {flexRender(
                         cell.column.columnDef.cell,
                         cell.getContext()
                       )}
                     </TableCell>
                   ))}
                 </TableRow>
               ))
             ) : (
               <TableRow>
                 <TableCell
                   colSpan={columns.length}
                   className="h-24 text-center"
                 >
                   No verifications pending.
                 </TableCell>
               </TableRow>
             )}
           </TableBody>
         </Table>
       </div>
     );
   }

   // Helper functions
   function getTypeIcon(type: string): JSX.Element {
     const iconMap: Record<string, string> = {
       contradiction: '⚡',
       citation: '⚖️',
       timeline: '📅',
       entity: '👤',
       summary: '📋',
     };
     return <span>{iconMap[type.toLowerCase()] ?? '📄'}</span>;
   }

   function formatFindingType(type: string): string {
     return type
       .replace(/_/g, ' ')
       .replace(/\b\w/g, (c) => c.toUpperCase());
   }

   function getConfidenceColor(confidence: number): string {
     if (confidence > 90) return '[&>div]:bg-green-500';
     if (confidence > 70) return '[&>div]:bg-yellow-500';
     return '[&>div]:bg-red-500';
   }
   ```

6. **Statistics Header Component**

   ```typescript
   // frontend/src/components/features/verification/VerificationStats.tsx

   'use client';

   import { Progress } from '@/components/ui/progress';
   import { Badge } from '@/components/ui/badge';
   import { Button } from '@/components/ui/button';
   import type { VerificationStats as StatsType } from '@/types/verification';

   interface VerificationStatsProps {
     stats: StatsType;
     onStartSession?: () => void;
   }

   export function VerificationStats({
     stats,
     onStartSession,
   }: VerificationStatsProps) {
     const completionPercent = stats.totalVerifications > 0
       ? Math.round(
           ((stats.approvedCount + stats.rejectedCount) /
             stats.totalVerifications) *
             100
         )
       : 0;

     return (
       <div className="space-y-4 p-4 rounded-lg border bg-card">
         <div className="flex items-center justify-between">
           <div>
             <h2 className="text-lg font-semibold">Verification Center</h2>
             <Progress value={completionPercent} className="w-64 h-2 mt-2" />
             <p className="text-sm text-muted-foreground mt-1">
               {completionPercent}% Complete
             </p>
           </div>
           {onStartSession && (
             <Button onClick={onStartSession}>
               Start Review Session
             </Button>
           )}
         </div>

         <div className="flex items-center gap-4 text-sm">
           <span>{stats.approvedCount} verified</span>
           <span className="text-muted-foreground">•</span>
           <span>{stats.pendingCount} pending</span>
           <span className="text-muted-foreground">•</span>
           <span>{stats.flaggedCount} flagged</span>
           {stats.exportBlocked && (
             <>
               <span className="text-muted-foreground">•</span>
               <Badge variant="destructive">
                 {stats.blockingCount} blocking export
               </Badge>
             </>
           )}
         </div>

         <div className="flex gap-2">
           <Badge variant="outline">
             Summary: {stats.requiredPending + stats.suggestedPending}
           </Badge>
           <Badge variant="outline">Timeline: {stats.requiredPending}</Badge>
           <Badge variant="outline">Entity: {stats.optionalPending}</Badge>
           <Badge variant="outline">Citation: {stats.suggestedPending}</Badge>
           <Badge variant="outline">
             Contradiction: {stats.requiredPending}
           </Badge>
         </div>
       </div>
     );
   }
   ```

7. **Rejection Dialog Component**

   ```typescript
   // frontend/src/components/features/verification/RejectDialog.tsx

   'use client';

   import { useState } from 'react';
   import {
     Dialog,
     DialogContent,
     DialogDescription,
     DialogFooter,
     DialogHeader,
     DialogTitle,
   } from '@/components/ui/dialog';
   import { Button } from '@/components/ui/button';
   import { Textarea } from '@/components/ui/textarea';
   import { Label } from '@/components/ui/label';

   interface RejectDialogProps {
     open: boolean;
     onOpenChange: (open: boolean) => void;
     onConfirm: (notes: string) => void;
     findingSummary: string;
   }

   export function RejectDialog({
     open,
     onOpenChange,
     onConfirm,
     findingSummary,
   }: RejectDialogProps) {
     const [notes, setNotes] = useState('');

     const handleConfirm = () => {
       if (notes.trim()) {
         onConfirm(notes.trim());
         setNotes('');
         onOpenChange(false);
       }
     };

     return (
       <Dialog open={open} onOpenChange={onOpenChange}>
         <DialogContent>
           <DialogHeader>
             <DialogTitle>Reject Finding</DialogTitle>
             <DialogDescription>
               Provide a reason for rejecting this finding:
               <br />
               <span className="font-medium">{findingSummary}</span>
             </DialogDescription>
           </DialogHeader>
           <div className="space-y-2">
             <Label htmlFor="rejection-notes">
               Rejection Reason (required)
             </Label>
             <Textarea
               id="rejection-notes"
               placeholder="Explain why this finding is incorrect..."
               value={notes}
               onChange={(e) => setNotes(e.target.value)}
               rows={4}
             />
           </div>
           <DialogFooter>
             <Button variant="outline" onClick={() => onOpenChange(false)}>
               Cancel
             </Button>
             <Button
               variant="destructive"
               onClick={handleConfirm}
               disabled={!notes.trim()}
             >
               Reject Finding
             </Button>
           </DialogFooter>
         </DialogContent>
       </Dialog>
     );
   }
   ```

### Existing Code to Reuse (DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `finding_verifications` table | Story 8-4 migration | Backend table structure |
| `VerificationService` | `services/verification/verification_service.py` | Backend API |
| `VerificationStats` model | `models/verification.py` | Backend Pydantic models |
| `verifications` API routes | `api/routes/verifications.py` | Backend endpoints |
| shadcn/ui DataTable | `components/ui/table.tsx` | Base table component |
| shadcn/ui Progress | `components/ui/progress.tsx` | Progress bar |
| shadcn/ui Dialog | `components/ui/dialog.tsx` | Modal dialogs |
| shadcn/ui Checkbox | `components/ui/checkbox.tsx` | Selection checkboxes |
| Matter workspace layout | `app/(matter)/[matterId]/layout.tsx` | Parent layout |
| API client base | `lib/api/client.ts` | HTTP client pattern |

### Previous Story (8-4) Implementation

From Story 8-4, the backend provides:

**API Endpoints Available:**
- `GET /api/matters/{matter_id}/verifications` - List all verifications
- `GET /api/matters/{matter_id}/verifications/pending` - Pending queue
- `GET /api/matters/{matter_id}/verifications/stats` - Statistics
- `POST /api/matters/{matter_id}/verifications/{verification_id}/approve`
- `POST /api/matters/{matter_id}/verifications/{verification_id}/reject`
- `POST /api/matters/{matter_id}/verifications/{verification_id}/flag`
- `POST /api/matters/{matter_id}/verifications/bulk` - Bulk operations

**Request Body Models (from Story 8-4 code review):**
```python
class ApproveVerificationRequest(BaseModel):
    notes: str | None = None
    confidence_after: float | None = Field(None, ge=0, le=100)

class RejectVerificationRequest(BaseModel):
    notes: str = Field(..., min_length=1)

class FlagVerificationRequest(BaseModel):
    notes: str | None = None
```

### Git Intelligence

Recent commit patterns for Epic 8:
- `feat(safety): implement finding verifications table (Story 8-4)`
- `fix(review): code review fixes for Story 8-4`
- `feat(safety): implement language policing output sanitization (Story 8-3)`

Use: `feat(safety): implement verification queue UI (Story 8-5)`

### File Structure

```
frontend/src/
├── app/
│   └── (matter)/
│       └── [matterId]/
│           └── verification/
│               ├── page.tsx           # NEW: Main verification page
│               ├── loading.tsx        # NEW: Loading state
│               └── error.tsx          # NEW: Error boundary
├── components/
│   └── features/
│       └── verification/
│           ├── VerificationStats.tsx     # NEW: Statistics header
│           ├── VerificationStats.test.tsx
│           ├── VerificationQueue.tsx     # NEW: DataTable component
│           ├── VerificationQueue.test.tsx
│           ├── VerificationActions.tsx   # NEW: Bulk action toolbar
│           ├── VerificationFilters.tsx   # NEW: Filter controls
│           ├── RejectDialog.tsx          # NEW: Rejection modal
│           └── FlagDialog.tsx            # NEW: Flag modal
├── lib/
│   └── api/
│       └── verifications.ts             # NEW: API client
├── stores/
│   └── verificationStore.ts             # NEW: Zustand store
├── hooks/
│   ├── useVerificationQueue.ts          # NEW: Queue hook
│   ├── useVerificationStats.ts          # NEW: Stats hook
│   └── useVerificationActions.ts        # NEW: Actions hook
└── types/
    └── verification.ts                  # NEW: TypeScript types
```

### Testing Requirements

Per project-context.md:
- Frontend: Co-locate tests with components
- Test behavior, not implementation
- Use `screen` queries, prefer `getByRole`
- Mock API calls with MSW

**Minimum Test Cases:**

```typescript
// VerificationQueue.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { VerificationQueue } from './VerificationQueue';

const mockData = [
  {
    id: 'ver-1',
    findingId: 'find-1',
    findingType: 'citation',
    findingSummary: 'Section 138 mismatch',
    confidence: 65,
    requirement: 'required',
    decision: 'pending',
    createdAt: '2026-01-14T00:00:00Z',
    sourceDocument: 'Petition.pdf pg 45',
    engine: 'citation',
  },
  {
    id: 'ver-2',
    findingId: 'find-2',
    findingType: 'entity',
    findingSummary: 'J. Kumar alias',
    confidence: 87,
    requirement: 'suggested',
    decision: 'pending',
    createdAt: '2026-01-14T00:00:00Z',
    sourceDocument: null,
    engine: 'entity',
  },
];

describe('VerificationQueue', () => {
  it('renders queue items with correct data', () => {
    render(
      <VerificationQueue
        data={mockData}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onFlag={vi.fn()}
        selectedIds={[]}
        onToggleSelect={vi.fn()}
        onSelectAll={vi.fn()}
      />
    );

    expect(screen.getByText('Section 138 mismatch')).toBeInTheDocument();
    expect(screen.getByText('J. Kumar alias')).toBeInTheDocument();
  });

  it('displays confidence with correct color', () => {
    render(
      <VerificationQueue
        data={mockData}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onFlag={vi.fn()}
        selectedIds={[]}
        onToggleSelect={vi.fn()}
        onSelectAll={vi.fn()}
      />
    );

    // Low confidence (65%) should show red
    expect(screen.getByText('65%')).toBeInTheDocument();
    // Medium confidence (87%) should show yellow
    expect(screen.getByText('87%')).toBeInTheDocument();
  });

  it('calls onApprove when approve button clicked', async () => {
    const onApprove = vi.fn();
    render(
      <VerificationQueue
        data={mockData}
        onApprove={onApprove}
        onReject={vi.fn()}
        onFlag={vi.fn()}
        selectedIds={[]}
        onToggleSelect={vi.fn()}
        onSelectAll={vi.fn()}
      />
    );

    const approveButtons = screen.getAllByRole('button', { name: /approve/i });
    fireEvent.click(approveButtons[0]);

    expect(onApprove).toHaveBeenCalledWith('ver-1');
  });

  it('toggles row selection on checkbox click', () => {
    const onToggleSelect = vi.fn();
    render(
      <VerificationQueue
        data={mockData}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onFlag={vi.fn()}
        selectedIds={[]}
        onToggleSelect={onToggleSelect}
        onSelectAll={vi.fn()}
      />
    );

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]); // First row checkbox (index 0 is header)

    expect(onToggleSelect).toHaveBeenCalledWith('ver-1');
  });

  it('shows empty state when no data', () => {
    render(
      <VerificationQueue
        data={[]}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onFlag={vi.fn()}
        selectedIds={[]}
        onToggleSelect={vi.fn()}
        onSelectAll={vi.fn()}
      />
    );

    expect(screen.getByText(/no verifications pending/i)).toBeInTheDocument();
  });
});
```

### Security Considerations

1. **Matter Isolation**: All API calls include matter_id in path, RLS enforced on backend
2. **Audit Trail**: All verification decisions timestamped with user ID (backend handles)
3. **Role Enforcement**: API endpoints validate user role (Editor/Owner required)
4. **Optimistic Updates**: Show immediate feedback but rollback on API failure

### Integration Points

1. **Story 8-4**: Backend verification service and API endpoints
2. **Matter Workspace**: Tab bar navigation integration
3. **Story 12-3**: Export eligibility check (export blocked if unverified low-confidence)
4. **Q&A Panel**: AI mentions verification status when relevant

### Dependencies

This story depends on:
- **Story 8-4**: Finding verifications table and backend API (DONE)
- **Matter workspace layout**: Tab navigation (exists)
- **shadcn/ui components**: DataTable, Dialog, Progress (exists)

This story is standalone for Epic 8 completion.

### Critical NFR Compliance

**NFR23: Court-defensible verification workflow with forensic trail**

Frontend contribution to court-defensibility:
1. Clear UI for attorney verification decisions
2. Required notes field for rejections (enforced in dialog)
3. Visual confidence indicators guiding review priority
4. Bulk operations for efficient review with audit trail

### Project Structure Notes

- New page under Matter workspace at `/[matterId]/verification`
- New components in `features/verification/` directory
- New Zustand store for verification state
- New API client following existing patterns
- Tests co-located with components

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, Zustand patterns
- [Architecture: ADR-004](_bmad-output/architecture.md#adr-004-verification-tier-thresholds) - Tiered verification
- [UX Design: Verification Tab](_bmad-output/project-planning-artifacts/UX-Decisions-Log.md#12-matter-workspace---verification-tab) - Wireframes
- [Story 8-4](8-4-finding-verifications-table.md) - Backend implementation
- [FR10 Requirement](epics.md) - Attorney Verification Workflow
- [FR24 Requirement](epics.md) - Verification Tab

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **TypeScript Types**: Created comprehensive verification types in `frontend/src/types/verification.ts` with enums matching backend (VerificationDecision, VerificationRequirement) and interfaces for queue items, stats, and filters.

2. **API Client**: Implemented `frontend/src/lib/api/verifications.ts` with all endpoints: getVerificationStats, getPendingQueue, getVerifications, approveVerification, rejectVerification, flagVerification, and bulkUpdateVerifications.

3. **Zustand Store**: Created `frontend/src/stores/verificationStore.ts` following project patterns with selectors. Includes helper functions for confidence tiers, color coding, and finding type formatting.

4. **Custom Hooks**: Created three hooks for data fetching and actions:
   - `useVerificationQueue` - Queue fetching with polling
   - `useVerificationStats` - Stats fetching with polling
   - `useVerificationActions` - Actions with optimistic updates

5. **Components**: Created six verification feature components:
   - `VerificationPage` - Main page orchestrator
   - `VerificationStats` - Statistics header with progress bar
   - `VerificationQueue` - DataTable with sorting, selection, actions
   - `VerificationActions` - Bulk action toolbar
   - `VerificationFilters` - Filter dropdowns
   - `VerificationNotesDialog` - Modal for reject/flag notes

6. **Tests**: Created comprehensive tests (61 tests total):
   - `verificationStore.test.ts` - Store state and actions
   - `VerificationStats.test.tsx` - Statistics component
   - `VerificationQueue.test.tsx` - Queue table component

7. **Navigation**: Added verification route at `/[matterId]/verification`

8. **ADR-004 Compliance**: Implemented confidence tier thresholds:
   - >90%: Green (optional verification)
   - 70-90%: Yellow (suggested verification)
   - <70%: Red (required verification)

9. **Notes**: Did not use @tanstack/react-table as it wasn't installed; implemented native sorting with useState instead. Used vitest (not jest) per project configuration.

### File List

- `frontend/src/types/verification.ts` - NEW
- `frontend/src/types/index.ts` - MODIFIED (exports)
- `frontend/src/lib/api/verifications.ts` - NEW
- `frontend/src/stores/verificationStore.ts` - NEW
- `frontend/src/stores/verificationStore.test.ts` - NEW
- `frontend/src/stores/index.ts` - MODIFIED (exports)
- `frontend/src/hooks/useVerificationQueue.ts` - NEW
- `frontend/src/hooks/useVerificationStats.ts` - NEW
- `frontend/src/hooks/useVerificationActions.ts` - NEW
- `frontend/src/hooks/index.ts` - MODIFIED (exports)
- `frontend/src/components/features/verification/VerificationStats.tsx` - NEW
- `frontend/src/components/features/verification/VerificationStats.test.tsx` - NEW
- `frontend/src/components/features/verification/VerificationQueue.tsx` - NEW
- `frontend/src/components/features/verification/VerificationQueue.test.tsx` - NEW
- `frontend/src/components/features/verification/VerificationActions.tsx` - NEW
- `frontend/src/components/features/verification/VerificationFilters.tsx` - NEW
- `frontend/src/components/features/verification/VerificationNotesDialog.tsx` - NEW
- `frontend/src/components/features/verification/VerificationPage.tsx` - NEW
- `frontend/src/components/features/verification/index.ts` - NEW
- `frontend/src/app/(matter)/[matterId]/verification/page.tsx` - NEW
