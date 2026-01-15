'use client';

/**
 * EntitiesDetailPanel Component
 *
 * Slide-in panel showing detailed entity information when selected.
 * Enhanced with paginated mentions, document links, and alias management.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

import { useCallback, useState } from 'react';
import {
  User,
  Building2,
  Landmark,
  Package,
  X,
  Focus,
  FileText,
  Link2,
  BadgeCheck,
  AlertCircle,
  Loader2,
  ExternalLink,
  Plus,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { useEntityMentions } from '@/hooks/useEntities';
import type {
  EntityType,
  EntityWithRelations,
  RelationshipType,
  EntityMention,
} from '@/types/entity';

/**
 * Parameters for PDF viewer navigation
 */
export interface ViewInDocumentParams {
  documentId: string;
  pageNumber?: number;
  bboxIds?: string[];
  entityId?: string;
}

const entityTypeConfig: Record<
  EntityType,
  { icon: typeof User; color: string; label: string }
> = {
  PERSON: {
    icon: User,
    color: 'text-blue-600 dark:text-blue-400',
    label: 'Person',
  },
  ORG: {
    icon: Building2,
    color: 'text-green-600 dark:text-green-400',
    label: 'Organization',
  },
  INSTITUTION: {
    icon: Landmark,
    color: 'text-purple-600 dark:text-purple-400',
    label: 'Institution',
  },
  ASSET: {
    icon: Package,
    color: 'text-amber-600 dark:text-amber-400',
    label: 'Asset',
  },
};

const relationshipLabels: Record<RelationshipType, string> = {
  ALIAS_OF: 'Alias of',
  HAS_ROLE: 'Has role',
  RELATED_TO: 'Related to',
};

export interface EntitiesDetailPanelProps {
  entity: EntityWithRelations | null;
  matterId: string;
  isLoading?: boolean;
  error?: string | null;
  onClose: () => void;
  onEntitySelect: (entityId: string) => void;
  onFocusInGraph: () => void;
  onViewInDocument?: (params: ViewInDocumentParams) => void;
  onAddAlias?: (alias: string) => Promise<void>;
  className?: string;
}

export function EntitiesDetailPanel({
  entity,
  matterId,
  isLoading = false,
  error = null,
  onClose,
  onEntitySelect,
  onFocusInGraph,
  onViewInDocument,
  onAddAlias,
  className,
}: EntitiesDetailPanelProps) {
  const [mentionsPage, setMentionsPage] = useState(1);
  const [showAllMentions, setShowAllMentions] = useState(false);
  const [newAlias, setNewAlias] = useState('');
  const [isAddingAlias, setIsAddingAlias] = useState(false);
  const [addAliasMode, setAddAliasMode] = useState(false);

  // Fetch paginated mentions when entity is selected
  const {
    mentions,
    total: totalMentions,
    isLoading: mentionsLoading,
  } = useEntityMentions(matterId, entity?.id ?? null, {
    page: mentionsPage,
    perPage: showAllMentions ? 20 : 5,
    enabled: !!entity,
  });

  const handleLoadMoreMentions = useCallback(() => {
    if (!showAllMentions) {
      setShowAllMentions(true);
      setMentionsPage(1);
    } else {
      setMentionsPage((prev) => prev + 1);
    }
  }, [showAllMentions]);

  const handleCollapseMentions = useCallback(() => {
    setShowAllMentions(false);
    setMentionsPage(1);
  }, []);

  const handleAddAlias = useCallback(async () => {
    if (!newAlias.trim() || !onAddAlias) return;

    setIsAddingAlias(true);
    try {
      await onAddAlias(newAlias.trim());
      setNewAlias('');
      setAddAliasMode(false);
    } finally {
      setIsAddingAlias(false);
    }
  }, [newAlias, onAddAlias]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        handleAddAlias();
      } else if (e.key === 'Escape') {
        setAddAliasMode(false);
        setNewAlias('');
      }
    },
    [handleAddAlias]
  );

  const handleMentionClick = useCallback(
    (mention: EntityMention) => {
      if (onViewInDocument) {
        onViewInDocument({
          documentId: mention.documentId,
          pageNumber: mention.pageNumber ?? 1,
          bboxIds: mention.bboxIds,
          entityId: entity?.id,
        });
      }
    },
    [onViewInDocument, entity]
  );

  if (!entity && !isLoading && !error) {
    return null;
  }

  const config = entity ? entityTypeConfig[entity.entityType] : null;
  const Icon = config?.icon ?? User;
  const role = entity?.metadata?.roles?.[0];
  const confidence = entity?.metadata?.firstExtractionConfidence;

  // Use API-fetched mentions when available, fall back to recentMentions from entity detail
  const displayMentions = mentions.length > 0 ? mentions : (entity?.recentMentions ?? []);
  const displayTotal = mentions.length > 0 ? totalMentions : (entity?.mentionCount ?? 0);
  const hasMoreMentions = displayMentions.length < displayTotal;

  // Determine verification status
  const getVerificationStatus = () => {
    if (!entity) return null;

    // Check if entity has been manually verified
    const isVerified = entity.metadata?.verified === true;
    const isFlagged = entity.metadata?.flagged === true;

    if (isVerified) {
      return { status: 'verified', label: 'Verified', icon: BadgeCheck, color: 'text-green-600' };
    }
    if (isFlagged) {
      return { status: 'flagged', label: 'Flagged', icon: AlertTriangle, color: 'text-amber-600' };
    }
    return { status: 'pending', label: 'Pending', icon: Clock, color: 'text-muted-foreground' };
  };

  const verificationStatus = getVerificationStatus();

  return (
    <Card
      className={cn(
        'w-[360px] h-full flex flex-col border-l rounded-none shadow-lg',
        className
      )}
      role="complementary"
      aria-label="Entity details"
    >
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <div className="flex items-start gap-3">
          {isLoading ? (
            <Skeleton className="h-10 w-10 rounded-full" />
          ) : (
            <div
              className={cn(
                'flex h-10 w-10 items-center justify-center rounded-full bg-muted',
                config?.color
              )}
            >
              <Icon className="h-5 w-5" />
            </div>
          )}
          <div className="space-y-1">
            {isLoading ? (
              <>
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-24" />
              </>
            ) : entity ? (
              <>
                <CardTitle className="text-lg leading-tight">
                  {entity.canonicalName}
                </CardTitle>
                <CardDescription className="flex items-center gap-2 flex-wrap">
                  <Badge variant="secondary">{config?.label}</Badge>
                  {role && <Badge variant="outline">{role}</Badge>}
                </CardDescription>
              </>
            ) : null}
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel">
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>

      {error ? (
        <CardContent className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </CardContent>
      ) : isLoading ? (
        <CardContent className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      ) : entity ? (
        <ScrollArea className="flex-1">
          <CardContent className="space-y-6">
            {/* Confidence & Verification Status */}
            <div className="flex items-center justify-between">
              {confidence !== undefined && (
                <div className="flex items-center gap-2">
                  <BadgeCheck className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">
                    Confidence: {Math.round(confidence * 100)}%
                  </span>
                </div>
              )}
              {verificationStatus && (
                <Badge
                  variant={verificationStatus.status === 'verified' ? 'default' : 'secondary'}
                  className={cn('gap-1', verificationStatus.color)}
                >
                  <verificationStatus.icon className="h-3 w-3" />
                  {verificationStatus.label}
                </Badge>
              )}
            </div>

            {/* Aliases Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium">Aliases</h4>
                {onAddAlias && !addAliasMode && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setAddAliasMode(true)}
                    className="h-7 px-2 gap-1"
                    aria-label="Add alias"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add
                  </Button>
                )}
              </div>
              {entity.aliases.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {entity.aliases.map((alias, idx) => (
                    <Badge key={idx} variant="outline">
                      {alias}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No aliases</p>
              )}
              {addAliasMode && (
                <div className="flex items-center gap-2 mt-2">
                  <Input
                    placeholder="Enter alias..."
                    value={newAlias}
                    onChange={(e) => setNewAlias(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="h-8 text-sm"
                    autoFocus
                    disabled={isAddingAlias}
                    aria-label="New alias"
                  />
                  <Button
                    size="sm"
                    onClick={handleAddAlias}
                    disabled={!newAlias.trim() || isAddingAlias}
                    className="h-8"
                    aria-label="Confirm add alias"
                  >
                    {isAddingAlias ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setAddAliasMode(false);
                      setNewAlias('');
                    }}
                    className="h-8"
                    aria-label="Cancel add alias"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>

            <Separator />

            {/* Relationships Section */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium flex items-center gap-2">
                <Link2 className="h-4 w-4" />
                Relationships ({entity.relationships.length})
              </h4>
              {entity.relationships.length > 0 ? (
                <div className="space-y-2">
                  {entity.relationships.map((rel) => {
                    const isSource = rel.sourceEntityId === entity.id;
                    const targetId = isSource
                      ? rel.targetEntityId
                      : rel.sourceEntityId;
                    const targetName = isSource
                      ? rel.targetEntityName
                      : rel.sourceEntityName;

                    return (
                      <button
                        key={rel.id}
                        onClick={() => onEntitySelect(targetId)}
                        className="w-full text-left p-2 rounded-md hover:bg-muted transition-colors text-sm"
                      >
                        <span className="text-muted-foreground">
                          {relationshipLabels[rel.relationshipType]}:
                        </span>{' '}
                        <span className="font-medium">{targetName ?? targetId}</span>
                        <span className="text-xs text-muted-foreground ml-2">
                          ({Math.round(rel.confidence * 100)}%)
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No relationships found
                </p>
              )}
            </div>

            <Separator />

            {/* Mentions Section - Enhanced with pagination and document links */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Mentions ({displayTotal})
                </h4>
                {showAllMentions && displayMentions.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCollapseMentions}
                    className="h-7 px-2 gap-1"
                  >
                    <ChevronUp className="h-3.5 w-3.5" />
                    Collapse
                  </Button>
                )}
              </div>

              {mentionsLoading && displayMentions.length === 0 ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : displayMentions.length > 0 ? (
                <div className="space-y-2">
                  {displayMentions.map((mention) => (
                    <div
                      key={mention.id}
                      className={cn(
                        'p-2 rounded-md bg-muted/50 text-sm',
                        onViewInDocument && 'hover:bg-muted cursor-pointer transition-colors'
                      )}
                      onClick={() => handleMentionClick(mention)}
                      role={onViewInDocument ? 'button' : undefined}
                      tabIndex={onViewInDocument ? 0 : undefined}
                      onKeyDown={
                        onViewInDocument
                          ? (e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                handleMentionClick(mention);
                              }
                            }
                          : undefined
                      }
                    >
                      <p className="line-clamp-2">{mention.mentionText}</p>
                      <div className="flex items-center justify-between mt-1">
                        <p className="text-xs text-muted-foreground">
                          {mention.documentName ?? 'Unknown document'}
                          {mention.pageNumber && ` • Page ${mention.pageNumber}`}
                        </p>
                        {onViewInDocument && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 gap-1 text-xs"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleMentionClick(mention);
                            }}
                            aria-label={`View ${mention.documentName ?? 'document'} page ${mention.pageNumber ?? 1}`}
                          >
                            <ExternalLink className="h-3 w-3" />
                            View
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Load more / Show all button */}
                  {hasMoreMentions && (
                    <Button
                      variant="link"
                      size="sm"
                      className="px-0 gap-1"
                      onClick={handleLoadMoreMentions}
                      disabled={mentionsLoading}
                    >
                      {mentionsLoading ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                      {showAllMentions
                        ? `Load more (${displayMentions.length} of ${displayTotal})`
                        : `View all ${displayTotal} mentions`}
                    </Button>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No mentions available
                </p>
              )}
            </div>

            <Separator />

            {/* Actions */}
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-2"
                onClick={onFocusInGraph}
              >
                <Focus className="h-4 w-4" />
                Focus in Graph
              </Button>
            </div>
          </CardContent>
        </ScrollArea>
      ) : null}
    </Card>
  );
}

EntitiesDetailPanel.displayName = 'EntitiesDetailPanel';
