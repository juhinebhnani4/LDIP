/**
 * AddEventDialog Component
 *
 * Dialog for creating manual timeline events.
 * Attorneys can add events that aren't in documents.
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

'use client';

import { useState, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { format } from 'date-fns';
import { CalendarIcon, Info, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type { ManualEventCreateRequest, TimelineEventType } from '@/types/timeline';
import { EVENT_TYPE_LABELS, EVENT_TYPE_ICONS } from './eventTypeIcons';

/**
 * Form values type for AddEvent form
 */
interface AddEventFormValues {
  eventDate: Date;
  eventType: 'filing' | 'notice' | 'hearing' | 'order' | 'transaction' | 'document' | 'deadline';
  title: string;
  description: string;
  entityIds: string[];
  sourceDocumentId: string | null;
  sourcePage: number | null;
}

/**
 * Zod schema for form validation
 */
const addEventSchema = z.object({
  eventDate: z.date({ message: 'Event date is required' }),
  eventType: z.enum(
    ['filing', 'notice', 'hearing', 'order', 'transaction', 'document', 'deadline'],
    { message: 'Event type is required' }
  ),
  title: z
    .string()
    .min(5, 'Title must be at least 5 characters')
    .max(200, 'Title cannot exceed 200 characters'),
  description: z
    .string()
    .max(2000, 'Description cannot exceed 2000 characters')
    .default(''),
  entityIds: z.array(z.string()).default([]),
  sourceDocumentId: z.string().nullable().optional(),
  sourcePage: z.coerce.number().int().positive().nullable().optional(),
});

/**
 * Entity option for actor selection
 */
interface EntityOption {
  id: string;
  name: string;
}

/**
 * Document option for source reference
 */
interface DocumentOption {
  id: string;
  name: string;
}

/**
 * AddEventDialog props
 */
interface AddEventDialogProps {
  /** Whether dialog is open */
  open: boolean;
  /** Callback to change open state */
  onOpenChange: (open: boolean) => void;
  /** Callback when event is created */
  onSubmit: (event: ManualEventCreateRequest) => Promise<void>;
  /** Available entities for actor selection */
  entities: EntityOption[];
  /** Available documents for source selection */
  documents: DocumentOption[];
}

/**
 * Event types available for manual events (exclude internal types)
 */
const MANUAL_EVENT_TYPES: TimelineEventType[] = [
  'filing',
  'notice',
  'hearing',
  'order',
  'transaction',
  'document',
  'deadline',
];

/**
 * AddEventDialog component
 */
export function AddEventDialog({
  open,
  onOpenChange,
  onSubmit,
  entities,
  documents,
}: AddEventDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm({
    resolver: zodResolver(addEventSchema),
    defaultValues: {
      eventType: undefined as AddEventFormValues['eventType'] | undefined,
      title: '',
      description: '',
      entityIds: [] as string[],
      sourceDocumentId: null as string | null,
      sourcePage: null as number | null,
    },
  });

  const handleSubmit = useCallback(
    async (values: AddEventFormValues) => {
      setIsSubmitting(true);
      try {
        await onSubmit({
          eventDate: format(values.eventDate, 'yyyy-MM-dd'),
          eventType: values.eventType,
          title: values.title,
          description: values.description ?? '',
          entityIds: values.entityIds ?? [],
          sourceDocumentId: values.sourceDocumentId ?? null,
          sourcePage: values.sourcePage ?? null,
        });
        toast.success('Event added successfully');
        form.reset();
        onOpenChange(false);
      } catch {
        toast.error('Failed to add event. Please try again.');
      } finally {
        setIsSubmitting(false);
      }
    },
    [form, onOpenChange, onSubmit]
  );

  const handleCancel = useCallback(() => {
    form.reset();
    onOpenChange(false);
  }, [form, onOpenChange]);

  // Handle entity selection
  const selectedEntityIds = form.watch('entityIds') ?? [];
  const handleEntityToggle = useCallback(
    (entityId: string) => {
      const current = form.getValues('entityIds') ?? [];
      if (current.includes(entityId)) {
        form.setValue(
          'entityIds',
          current.filter((id) => id !== entityId)
        );
      } else {
        form.setValue('entityIds', [...current, entityId]);
      }
    },
    [form]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Timeline Event</DialogTitle>
          <DialogDescription>
            Add an event that isn&apos;t captured in the documents.
          </DialogDescription>
        </DialogHeader>

        {/* Manual event info badge */}
        <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-950 rounded-lg border border-blue-200 dark:border-blue-800">
          <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0" />
          <span className="text-sm text-blue-700 dark:text-blue-300">
            This event will be marked as manually added
          </span>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit as Parameters<typeof form.handleSubmit>[0])} className="space-y-4">
            {/* Event Date Field */}
            <FormField
              control={form.control}
              name="eventDate"
              render={({ field }) => (
                <FormItem className="flex flex-col">
                  <FormLabel>
                    Event Date <span className="text-destructive">*</span>
                  </FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          variant="outline"
                          className={cn(
                            'w-full pl-3 text-left font-normal',
                            !field.value && 'text-muted-foreground'
                          )}
                          type="button"
                        >
                          {field.value ? (
                            format(field.value, 'PPP')
                          ) : (
                            <span>Pick a date</span>
                          )}
                          <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={field.value}
                        onSelect={field.onChange}
                        disabled={(date) =>
                          date > new Date() || date < new Date('1900-01-01')
                        }
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Event Type Field */}
            <FormField
              control={form.control}
              name="eventType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    Event Type <span className="text-destructive">*</span>
                  </FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select event type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {MANUAL_EVENT_TYPES.map((type) => {
                        const Icon = EVENT_TYPE_ICONS[type];
                        return (
                          <SelectItem key={type} value={type}>
                            <div className="flex items-center gap-2">
                              <Icon className="h-4 w-4" />
                              <span>{EVENT_TYPE_LABELS[type]}</span>
                            </div>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Title Field */}
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    Title <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Brief description of the event"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>5-200 characters</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Description Field */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Additional details about the event (optional)"
                      className="resize-none"
                      rows={3}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Actors Selection */}
            {entities.length > 0 && (
              <div className="space-y-3">
                <Label>Actors (optional)</Label>
                <div className="max-h-32 overflow-y-auto rounded-md border p-3 space-y-2">
                  {entities.map((entity) => (
                    <div key={entity.id} className="flex items-center space-x-2">
                      <Checkbox
                        id={`entity-${entity.id}`}
                        checked={selectedEntityIds.includes(entity.id)}
                        onCheckedChange={() => handleEntityToggle(entity.id)}
                      />
                      <Label
                        htmlFor={`entity-${entity.id}`}
                        className="text-sm font-normal cursor-pointer"
                      >
                        {entity.name}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Source Document Selection */}
            {documents.length > 0 && (
              <div className="space-y-3">
                <FormField
                  control={form.control}
                  name="sourceDocumentId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Source Document (optional)</FormLabel>
                      <Select
                        onValueChange={(value) =>
                          field.onChange(value === 'none' ? null : value)
                        }
                        value={field.value ?? 'none'}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select source document" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">No source document</SelectItem>
                          {documents.map((doc) => (
                            <SelectItem key={doc.id} value={doc.id}>
                              {doc.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Page Number (only shown when document selected) */}
                {form.watch('sourceDocumentId') && (
                  <FormField
                    control={form.control}
                    name="sourcePage"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Page Number (optional)</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={1}
                            placeholder="e.g., 5"
                            {...field}
                            value={typeof field.value === 'number' ? field.value : ''}
                            onChange={(e) =>
                              field.onChange(
                                e.target.value ? parseInt(e.target.value, 10) : null
                              )
                            }
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
              </div>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  'Add Event'
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

export default AddEventDialog;
