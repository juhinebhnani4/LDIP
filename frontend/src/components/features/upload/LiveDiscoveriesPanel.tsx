'use client';

/**
 * LiveDiscoveriesPanel Component
 *
 * Displays live discoveries during processing - entities, dates, citations,
 * timeline preview, and early insights. Updates in real-time as processing
 * progresses with fade-in animations.
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 */

import { useMemo } from 'react';
import {
  Users,
  Calendar,
  Scale,
  Lightbulb,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type {
  LiveDiscovery,
  DiscoveredEntity,
  DiscoveredDate,
  DiscoveredCitation,
  EarlyInsight,
} from '@/types/upload';

interface LiveDiscoveriesPanelProps {
  /** All discoveries from processing */
  discoveries: LiveDiscovery[];
  /** Optional className */
  className?: string;
}

/** Format a date for display */
function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

/** Entities section */
function EntitiesSection({ entities, count }: { entities: DiscoveredEntity[]; count: number }) {
  const displayEntities = entities.slice(0, 3);
  const moreCount = count > 3 ? count - 3 : 0;

  return (
    <div className="space-y-2 animate-fade-in">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Users className="size-4 text-blue-600" />
        <span>ENTITIES FOUND ({count})</span>
      </div>
      <ul className="space-y-1 pl-6 text-sm text-muted-foreground">
        {displayEntities.map((entity) => (
          <li key={`${entity.name}-${entity.role}`} className="flex items-center gap-1">
            <span className="font-medium text-foreground">{entity.name}</span>
            {entity.role && (
              <span className="text-xs">({entity.role})</span>
            )}
          </li>
        ))}
        {moreCount > 0 && (
          <li className="text-xs">+{moreCount} more...</li>
        )}
      </ul>
    </div>
  );
}

/** Dates section */
function DatesSection({ dateInfo, count }: { dateInfo: DiscoveredDate; count: number }) {
  return (
    <div className="space-y-2 animate-fade-in">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Calendar className="size-4 text-amber-600" />
        <span>DATES EXTRACTED ({count})</span>
      </div>
      <div className="pl-6 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Earliest:</span>
          <span className="font-medium">{formatDate(dateInfo.earliest)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Latest:</span>
          <span className="font-medium">{formatDate(dateInfo.latest)}</span>
        </div>
      </div>
    </div>
  );
}

/** Citations section */
function CitationsSection({
  citations,
  count,
}: {
  citations: DiscoveredCitation[];
  count: number;
}) {
  return (
    <div className="space-y-2 animate-fade-in">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Scale className="size-4 text-purple-600" />
        <span>CITATIONS DETECTED ({count})</span>
      </div>
      <ul className="space-y-1 pl-6 text-sm">
        {citations.map((citation) => (
          <li
            key={citation.actName}
            className="flex items-center justify-between text-muted-foreground"
          >
            <span>{citation.actName}</span>
            <span className="font-medium text-foreground">({citation.count})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Mini timeline preview */
function MiniTimelinePreview({ dateInfo }: { dateInfo: DiscoveredDate }) {
  const startYear = dateInfo.earliest.getFullYear();
  const endYear = dateInfo.latest.getFullYear();
  const yearSpan = endYear - startYear;

  // Calculate dot positions (0-100%)
  const dots = useMemo(() => {
    if (yearSpan === 0) {
      return [{ position: 50, label: startYear.toString() }];
    }

    // Create 3-5 dots representing date clusters
    const numDots = Math.min(5, Math.max(3, Math.ceil(yearSpan / 2)));
    const result = [];

    for (let i = 0; i < numDots; i++) {
      const ratio = i / (numDots - 1);
      const position = ratio * 100;
      const year = Math.round(startYear + ratio * yearSpan);
      result.push({ position, label: year.toString() });
    }

    return result;
  }, [startYear, yearSpan]);

  return (
    <Card className="animate-fade-in">
      <CardHeader className="py-2 px-3">
        <CardTitle className="text-xs font-medium flex items-center gap-1.5">
          <Clock className="size-3.5 text-muted-foreground" />
          TIMELINE PREVIEW
        </CardTitle>
      </CardHeader>
      <CardContent className="px-3 pb-3 pt-0">
        <div className="relative h-8">
          {/* Timeline line */}
          <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-muted-foreground/30 -translate-y-1/2" />

          {/* Timeline dots */}
          {dots.map((dot, index) => (
            <div
              key={dot.label + index}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center"
              style={{ left: `${dot.position}%` }}
            >
              <div
                className={cn(
                  'size-2.5 rounded-full',
                  index === 0 || index === dots.length - 1
                    ? 'bg-primary'
                    : 'bg-muted-foreground/50'
                )}
              />
              <span className="text-[10px] text-muted-foreground mt-1.5 whitespace-nowrap">
                {dot.label}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/** Early insights section */
function EarlyInsightsSection({ insights }: { insights: EarlyInsight[] }) {
  return (
    <Card className="animate-fade-in">
      <CardHeader className="py-2 px-3">
        <CardTitle className="text-xs font-medium flex items-center gap-1.5">
          <Lightbulb className="size-3.5 text-amber-500" />
          EARLY INSIGHTS
        </CardTitle>
      </CardHeader>
      <CardContent className="px-3 pb-3 pt-0 space-y-2">
        {insights.map((insight, index) => (
          <div
            key={`insight-${index}`}
            className={cn(
              'flex items-start gap-2 p-2 rounded-md text-sm',
              insight.type === 'info' && 'bg-blue-50 dark:bg-blue-950/30',
              insight.type === 'warning' && 'bg-amber-50 dark:bg-amber-950/30'
            )}
          >
            {insight.icon === 'lightbulb' ? (
              <Lightbulb className="size-4 text-blue-600 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="size-4 text-amber-600 flex-shrink-0 mt-0.5" />
            )}
            <span
              className={cn(
                insight.type === 'info' && 'text-blue-800 dark:text-blue-200',
                insight.type === 'warning' && 'text-amber-800 dark:text-amber-200'
              )}
            >
              {insight.message}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function LiveDiscoveriesPanel({
  discoveries,
  className,
}: LiveDiscoveriesPanelProps) {
  // Extract different discovery types
  const { entities, entityCount, dateInfo, dateCount, citations, citationCount, insights } =
    useMemo(() => {
      let allEntities: DiscoveredEntity[] = [];
      let allCitations: DiscoveredCitation[] = [];
      let dateData: DiscoveredDate | null = null;
      const insightsList: EarlyInsight[] = [];
      let totalEntityCount = 0;
      let totalDateCount = 0;
      let totalCitationCount = 0;

      for (const discovery of discoveries) {
        switch (discovery.type) {
          case 'entity':
            allEntities = discovery.details as DiscoveredEntity[];
            totalEntityCount = discovery.count;
            break;
          case 'date':
            dateData = discovery.details as DiscoveredDate;
            totalDateCount = discovery.count;
            break;
          case 'citation':
            allCitations = discovery.details as DiscoveredCitation[];
            totalCitationCount = discovery.count;
            break;
          case 'insight':
            insightsList.push(discovery.details as EarlyInsight);
            break;
        }
      }

      return {
        entities: allEntities,
        entityCount: totalEntityCount,
        dateInfo: dateData,
        dateCount: totalDateCount,
        citations: allCitations,
        citationCount: totalCitationCount,
        insights: insightsList,
      };
    }, [discoveries]);

  const hasContent =
    entities.length > 0 ||
    dateInfo !== null ||
    citations.length > 0 ||
    insights.length > 0;

  return (
    <div className={cn('space-y-4', className)} aria-live="polite">
      {/* Main discoveries card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <span className="relative flex size-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full size-2 bg-green-500" />
            </span>
            LIVE DISCOVERIES
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {!hasContent && (
            <p className="text-sm text-muted-foreground text-center py-4">
              Analyzing documents... discoveries will appear here.
            </p>
          )}

          {entities.length > 0 && (
            <EntitiesSection entities={entities} count={entityCount} />
          )}

          {dateInfo && <DatesSection dateInfo={dateInfo} count={dateCount} />}

          {citations.length > 0 && (
            <CitationsSection citations={citations} count={citationCount} />
          )}
        </CardContent>
      </Card>

      {/* Timeline preview (separate card when dates available) */}
      {dateInfo && <MiniTimelinePreview dateInfo={dateInfo} />}

      {/* Early insights (separate card when available) */}
      {insights.length > 0 && <EarlyInsightsSection insights={insights} />}
    </div>
  );
}
