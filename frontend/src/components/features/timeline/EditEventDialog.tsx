/**
 * EditEventDialog Component
 *
 * Dialog for editing timeline events.
 * - Manual events: Can edit all fields
 * - Auto-extracted events: Can only edit event type (classification correction)
 *
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { format, parseISO } from 'date-fns';
import { CalendarIcon, Loader2, User } from 'lucide-react';
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
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type {
  TimelineEvent,
  ManualEventUpdateRequest,
  TimelineEventType,
} from '@/types/timeline';
import { EVENT_TYPE_LABELS, EVENT_TYPE_ICONS } from './eventTypeIcons';

/**
 * Form values type for editing manual events
 */
interface EditManualFormValues {
  eventDate: Date;
  eventType: 'filing' | 'notice' | 'hearing' | 'order' | 'transaction' | 'document' | 'deadline';
  title: string;
  description: string;
  entityIds: string[];
}

/**
 * Form values type for editing auto events
 */
interface EditAutoFormValues {
  eventType: 'filing' | 'notice' | 'hearing' | 'order' | 'transaction' | 'document' | 'deadline';
}

/**
 * Zod schema for editing manual events
 */
const editManualEventSchema = z.object({
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
});

/**
 * Schema for editing auto-extracted events (classification only)
 */
const editAutoEventSchema = z.object({
  eventType: z.enum(
    ['filing', 'notice', 'hearing', 'order', 'transaction', 'document', 'deadline'],
    { message: 'Event type is required' }
  ),
});

/**
 * Entity option for actor selection
 */
interface EntityOption {
  id: string;
  name: string;
}

/**
 * EditEventDialog props
 */
interface EditEventDialogProps {
  /** Whether dialog is open */
  open: boolean;
  /** Callback to change open state */
  onOpenChange: (open: boolean) => void;
  /** Event to edit */
  event: TimelineEvent | null;
  /** Callback when event is updated */
  onSubmit: (eventId: string, updates: ManualEventUpdateRequest) => Promise<void>;
  /** Available entities for actor selection */
  entities: EntityOption[];
}

/**
 * Event types available for editing
 */
const EVENT_TYPES: TimelineEventType[] = [
  'filing',
  'notice',
  'hearing',
  'order',
  'transaction',
  'document',
  'deadline',
];

/**
 * EditEventDialog component
 */
export function EditEventDialog({
  open,
  onOpenChange,
  event,
  onSubmit,
  entities,
}: EditEventDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isManualEvent = event?.isManual === true;

  // Form for manual events (full edit)
  const manualForm = useForm({
    resolver: zodResolver(editManualEventSchema),
    defaultValues: {
      eventType: undefined as EditManualFormValues['eventType'] | undefined,
      title: '',
      description: '',
      entityIds: [] as string[],
    },
  });

  // Form for auto events (classification only)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const autoForm = useForm({
    resolver: zodResolver(editAutoEventSchema) as any,
    defaultValues: {
      eventType: undefined as EditAutoFormValues['eventType'] | undefined,
    },
  });

  // Update form when event changes
  useEffect(() => {
    if (event && open) {
      if (isManualEvent) {
        manualForm.reset({
          eventDate: parseISO(event.eventDate),
          eventType: event.eventType as EditManualFormValues['eventType'],
          title: event.description,
          description: '',
          entityIds: event.entities.map((e) => e.entityId),
        });
      } else {
        autoForm.reset({
          eventType: event.eventType as EditAutoFormValues['eventType'],
        });
      }
    }
  }, [event, open, isManualEvent, manualForm, autoForm]);

  const handleManualSubmit = useCallback(
    async (values: EditManualFormValues) => {
      if (!event) return;
      setIsSubmitting(true);
      try {
        await onSubmit(event.id, {
          eventDate: format(values.eventDate, 'yyyy-MM-dd'),
          eventType: values.eventType,
          title: values.title,
          description: values.description ?? '',
          entityIds: values.entityIds ?? [],
        });
        toast.success('Event updated successfully');
        onOpenChange(false);
      } catch {
        toast.error('Failed to update event. Please try again.');
      } finally {
        setIsSubmitting(false);
      }
    },
    [event, onOpenChange, onSubmit]
  );

  const handleAutoSubmit = useCallback(
    async (values: EditAutoFormValues) => {
      if (!event) return;
      setIsSubmitting(true);
      try {
        await onSubmit(event.id, {
          eventType: values.eventType,
        });
        toast.success('Event classification updated');
        onOpenChange(false);
      } catch {
        toast.error('Failed to update event. Please try again.');
      } finally {
        setIsSubmitting(false);
      }
    },
    [event, onOpenChange, onSubmit]
  );

  const handleCancel = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  // Handle entity selection for manual form
  const selectedEntityIds = manualForm.watch('entityIds') ?? [];
  const handleEntityToggle = useCallback(
    (entityId: string) => {
      const current = manualForm.getValues('entityIds') ?? [];
      if (current.includes(entityId)) {
        manualForm.setValue(
          'entityIds',
          current.filter((id) => id !== entityId)
        );
      } else {
        manualForm.setValue('entityIds', [...current, entityId]);
      }
    },
    [manualForm]
  );

  if (!event) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {isManualEvent ? 'Edit Manual Event' : 'Edit Event Classification'}
          </DialogTitle>
          <DialogDescription>
            {isManualEvent
              ? 'Update the details of this manually added event.'
              : 'Correct the classification of this auto-extracted event.'}
          </DialogDescription>
        </DialogHeader>

        {/* Event origin badge */}
        <div className="flex items-center gap-2">
          <Badge variant={isManualEvent ? 'default' : 'secondary'}>
            <User className="h-3 w-3 mr-1" />
            {isManualEvent ? 'Manually added' : 'Auto-extracted'}
          </Badge>
          {!isManualEvent && (
            <span className="text-sm text-muted-foreground">
              Only event type can be modified
            </span>
          )}
        </div>

        {isManualEvent ? (
          /* Full edit form for manual events */
          <Form {...manualForm}>
            <form
              onSubmit={manualForm.handleSubmit(handleManualSubmit as Parameters<typeof manualForm.handleSubmit>[0])}
              className="space-y-4"
            >
              {/* Event Date Field */}
              <FormField
                control={manualForm.control}
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
                control={manualForm.control}
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
                        {EVENT_TYPES.map((type) => {
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
                control={manualForm.control}
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
                control={manualForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Additional details (optional)"
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
                          id={`edit-entity-${entity.id}`}
                          checked={selectedEntityIds.includes(entity.id)}
                          onCheckedChange={() => handleEntityToggle(entity.id)}
                        />
                        <Label
                          htmlFor={`edit-entity-${entity.id}`}
                          className="text-sm font-normal cursor-pointer"
                        >
                          {entity.name}
                        </Label>
                      </div>
                    ))}
                  </div>
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
                      Saving...
                    </>
                  ) : (
                    'Save Changes'
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        ) : (
          /* Classification-only form for auto events */
          <Form {...autoForm}>
            <form
              onSubmit={autoForm.handleSubmit(handleAutoSubmit as Parameters<typeof autoForm.handleSubmit>[0])}
              className="space-y-4"
            >
              {/* Event Type Field */}
              <FormField
                control={autoForm.control}
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
                        {EVENT_TYPES.map((type) => {
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
                    <FormDescription>
                      Correct the event classification if it was misidentified
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

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
                      Saving...
                    </>
                  ) : (
                    'Update Classification'
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default EditEventDialog;
