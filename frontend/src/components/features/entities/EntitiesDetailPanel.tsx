'use client';

/**
 * EntitiesDetailPanel Component
 *
 * Slide-in panel showing detailed entity information when selected.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

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
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
import type {
  EntityType,
  EntityWithRelations,
  RelationshipType,
} from '@/types/entity';

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
  isLoading?: boolean;
  error?: string | null;
  onClose: () => void;
  onEntitySelect: (entityId: string) => void;
  onFocusInGraph: () => void;
  className?: string;
}

export function EntitiesDetailPanel({
  entity,
  isLoading = false,
  error = null,
  onClose,
  onEntitySelect,
  onFocusInGraph,
  className,
}: EntitiesDetailPanelProps) {
  if (!entity && !isLoading && !error) {
    return null;
  }

  const config = entity ? entityTypeConfig[entity.entityType] : null;
  const Icon = config?.icon ?? User;
  const role = entity?.metadata?.roles?.[0];
  const confidence = entity?.metadata?.firstExtractionConfidence;

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
                <CardDescription className="flex items-center gap-2">
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
            {/* Confidence & Verification */}
            {confidence !== undefined && (
              <div className="flex items-center gap-2">
                <BadgeCheck className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">
                  Confidence: {Math.round(confidence * 100)}%
                </span>
              </div>
            )}

            {/* Aliases Section */}
            {entity.aliases.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Aliases</h4>
                <div className="flex flex-wrap gap-2">
                  {entity.aliases.map((alias, idx) => (
                    <Badge key={idx} variant="outline">
                      {alias}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

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

            {/* Recent Mentions Section */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Recent Mentions
              </h4>
              {entity.recentMentions.length > 0 ? (
                <div className="space-y-2">
                  {entity.recentMentions.slice(0, 5).map((mention) => (
                    <div
                      key={mention.id}
                      className="p-2 rounded-md bg-muted/50 text-sm"
                    >
                      <p className="line-clamp-2">{mention.mentionText}</p>
                      {mention.documentName && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {mention.documentName}
                          {mention.pageNumber && ` • Page ${mention.pageNumber}`}
                        </p>
                      )}
                    </div>
                  ))}
                  {entity.recentMentions.length > 5 && (
                    <Button variant="link" size="sm" className="px-0">
                      See all {entity.mentionCount} mentions
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
