'use client';

import { useState, useMemo, useCallback } from 'react';
import { Search, X, ChevronRight, ExternalLink, RotateCcw } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  helpContent,
  helpCategories,
  searchHelpContent,
  getHelpEntriesByCategory,
  type HelpEntry,
} from '@/data/help-content';
import { useOnboardingTrigger } from '@/components/features/onboarding';

interface HelpPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type CategoryKey = keyof typeof helpCategories;

export function HelpPanel({ open, onOpenChange }: HelpPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntry, setSelectedEntry] = useState<HelpEntry | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey | null>(null);

  // Story 6.2: Restart tour functionality
  const { startOnboarding } = useOnboardingTrigger();

  const handleRestartTour = useCallback(() => {
    onOpenChange(false);
    startOnboarding();
  }, [onOpenChange, startOnboarding]);

  const searchResults = useMemo(() => {
    if (searchQuery.trim().length < 2) return [];
    return searchHelpContent(searchQuery);
  }, [searchQuery]);

  const categoryEntries = useMemo(() => {
    if (!selectedCategory) return [];
    return getHelpEntriesByCategory(selectedCategory);
  }, [selectedCategory]);

  const handleBack = useCallback(() => {
    if (selectedEntry) {
      setSelectedEntry(null);
    } else if (selectedCategory) {
      setSelectedCategory(null);
    }
  }, [selectedEntry, selectedCategory]);

  const handleSelectEntry = useCallback((entry: HelpEntry) => {
    setSelectedEntry(entry);
    setSearchQuery('');
  }, []);

  const handleSelectCategory = useCallback((category: CategoryKey) => {
    setSelectedCategory(category);
    setSelectedEntry(null);
    setSearchQuery('');
  }, []);

  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
  }, []);

  const showBackButton = selectedEntry !== null || selectedCategory !== null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md p-0 flex flex-col">
        <SheetHeader className="px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            {showBackButton && (
              <Button
                variant="ghost"
                size="icon"
                onClick={handleBack}
                className="h-8 w-8 -ml-2"
              >
                <ChevronRight className="h-4 w-4 rotate-180" />
                <span className="sr-only">Back</span>
              </Button>
            )}
            <SheetTitle className="text-lg">
              {selectedEntry
                ? selectedEntry.title
                : selectedCategory
                  ? helpCategories[selectedCategory].label
                  : 'Help Center'}
            </SheetTitle>
          </div>
        </SheetHeader>

        {!selectedEntry && (
          <div className="px-6 py-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search help topics..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-9"
              />
              {searchQuery && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleClearSearch}
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                >
                  <X className="h-3 w-3" />
                  <span className="sr-only">Clear search</span>
                </Button>
              )}
            </div>
          </div>
        )}

        <ScrollArea className="flex-1">
          <div className="p-6">
            {selectedEntry ? (
              <HelpEntryContent entry={selectedEntry} onSelectEntry={handleSelectEntry} />
            ) : searchQuery.trim().length >= 2 ? (
              <SearchResults
                results={searchResults}
                query={searchQuery}
                onSelectEntry={handleSelectEntry}
              />
            ) : selectedCategory ? (
              <CategoryContent
                entries={categoryEntries}
                onSelectEntry={handleSelectEntry}
              />
            ) : (
              <CategoryList onSelectCategory={handleSelectCategory} />
            )}
          </div>
        </ScrollArea>

        <div className="px-6 py-4 border-t bg-muted/50 space-y-3">
          {/* Story 6.2: Restart Tour button */}
          <Button
            variant="outline"
            size="sm"
            className="w-full gap-2"
            onClick={handleRestartTour}
          >
            <RotateCcw className="h-4 w-4" />
            Restart Product Tour
          </Button>
          <Separator />
          <p className="text-xs text-muted-foreground">
            Can&apos;t find what you need?{' '}
            <a
              href="https://github.com/your-org/ldip/issues/new?template=question.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              Contact support
              <ExternalLink className="h-3 w-3" />
            </a>
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function CategoryList({
  onSelectCategory,
}: {
  onSelectCategory: (category: CategoryKey) => void;
}) {
  const categories = Object.entries(helpCategories) as [CategoryKey, typeof helpCategories[CategoryKey]][];

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground mb-4">
        Browse help topics by category
      </p>
      {categories.map(([key, category]) => (
        <button
          key={key}
          onClick={() => onSelectCategory(key)}
          className="w-full text-left p-3 rounded-lg border hover:bg-accent transition-colors group"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{category.label}</p>
              <p className="text-sm text-muted-foreground">{category.description}</p>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
          </div>
        </button>
      ))}
    </div>
  );
}

function CategoryContent({
  entries,
  onSelectEntry,
}: {
  entries: HelpEntry[];
  onSelectEntry: (entry: HelpEntry) => void;
}) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No help topics in this category yet.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => (
        <button
          key={entry.id}
          onClick={() => onSelectEntry(entry)}
          className="w-full text-left p-3 rounded-lg border hover:bg-accent transition-colors group"
        >
          <div className="flex items-center justify-between">
            <p className="font-medium">{entry.title}</p>
            <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
          </div>
        </button>
      ))}
    </div>
  );
}

function SearchResults({
  results,
  query,
  onSelectEntry,
}: {
  results: HelpEntry[];
  query: string;
  onSelectEntry: (entry: HelpEntry) => void;
}) {
  if (results.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">
          No results found for &quot;{query}&quot;
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          Try different keywords or browse categories
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground mb-4">
        {results.length} result{results.length !== 1 ? 's' : ''} for &quot;{query}&quot;
      </p>
      {results.map((entry) => (
        <button
          key={entry.id}
          onClick={() => onSelectEntry(entry)}
          className="w-full text-left p-3 rounded-lg border hover:bg-accent transition-colors group"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{entry.title}</p>
              <p className="text-xs text-muted-foreground capitalize">
                {helpCategories[entry.category].label}
              </p>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
          </div>
        </button>
      ))}
    </div>
  );
}

function HelpEntryContent({
  entry,
  onSelectEntry,
}: {
  entry: HelpEntry;
  onSelectEntry: (entry: HelpEntry) => void;
}) {
  const relatedEntries = useMemo(() => {
    if (!entry.relatedTopics) return [];
    return entry.relatedTopics
      .map((id) => helpContent.find((e) => e.id === id))
      .filter((e): e is HelpEntry => e !== undefined);
  }, [entry.relatedTopics]);

  return (
    <div className="space-y-6">
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <div
          dangerouslySetInnerHTML={{
            __html: formatMarkdown(entry.content),
          }}
        />
      </div>

      {relatedEntries.length > 0 && (
        <div className="pt-4 border-t">
          <p className="text-sm font-medium mb-2">Related Topics</p>
          <div className="space-y-1">
            {relatedEntries.map((related) => (
              <button
                key={related.id}
                onClick={() => onSelectEntry(related)}
                className="w-full text-left text-sm p-2 rounded hover:bg-accent transition-colors text-primary"
              >
                {related.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function formatMarkdown(content: string): string {
  return content
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-semibold mt-4 mb-2">$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-medium mt-3 mb-1">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-muted px-1 py-0.5 rounded text-sm">$1</code>')
    .replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal">$2</li>')
    .replace(/\n\n/g, '</p><p class="mt-2">')
    .replace(/\n/g, '<br/>')
    .replace(/<li/g, '<ul class="my-2"><li')
    .replace(/<\/li>(?!<li)/g, '</li></ul>')
    .replace(/<\/ul><ul[^>]*>/g, '')
    .replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').filter(Boolean);
      const isHeader = cells.some((c) => c.includes('---'));
      if (isHeader) return '';
      return `<tr>${cells.map((c) => `<td class="border px-2 py-1">${c.trim()}</td>`).join('')}</tr>`;
    });
}
