'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Search, FileText, Briefcase, X, AlertCircle, RefreshCw } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverAnchor,
} from '@/components/ui/popover';
import { toast } from 'sonner';
import { globalSearch, type SearchResult } from '@/lib/api/globalSearch';

/** Debounce delay in milliseconds */
const DEBOUNCE_DELAY = 300;

interface SearchResultItemProps {
  result: SearchResult;
  onSelect: (result: SearchResult) => void;
}

function SearchResultItem({ result, onSelect }: SearchResultItemProps) {
  const Icon = result.type === 'matter' ? Briefcase : FileText;

  return (
    <button
      type="button"
      className="flex w-full items-start gap-3 rounded-md p-2 text-left hover:bg-accent focus:bg-accent focus:outline-none"
      onClick={() => onSelect(result)}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="flex-1 overflow-hidden">
        <p className="truncate text-sm font-medium">{result.title}</p>
        <p className="truncate text-xs text-muted-foreground">{result.matterTitle}</p>
        <p className="line-clamp-1 text-xs text-muted-foreground">{result.matchedContent}</p>
      </div>
    </button>
  );
}

export function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastQueryRef = useRef<string>('');

  // Debounced search function
  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setResults([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    lastQueryRef.current = searchQuery;
    setIsLoading(true);
    setError(null);

    try {
      const searchResults = await globalSearch(searchQuery);
      // Only update if this is still the current query
      if (lastQueryRef.current === searchQuery) {
        setResults(searchResults);
      }
    } catch (err) {
      // Only update if this is still the current query
      if (lastQueryRef.current === searchQuery) {
        setResults([]);
        const message = err instanceof Error ? err.message : 'Search failed';
        setError(message);
        toast.error('Search failed. Please try again.');
      }
    } finally {
      if (lastQueryRef.current === searchQuery) {
        setIsLoading(false);
      }
    }
  }, []);

  // Retry search on error
  const handleRetry = useCallback(() => {
    if (query.trim()) {
      performSearch(query);
    }
  }, [query, performSearch]);

  // Handle input change with debouncing
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newQuery = e.target.value;
      setQuery(newQuery);

      // Clear existing timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // Set new timer for debounced search
      debounceTimerRef.current = setTimeout(() => {
        performSearch(newQuery);
      }, DEBOUNCE_DELAY);
    },
    [performSearch]
  );

  // Handle result selection
  const handleResultSelect = useCallback((result: SearchResult) => {
    setIsOpen(false);
    setQuery('');
    setResults([]);
    setError(null);

    // Navigate based on type
    if (result.type === 'matter') {
      window.location.href = `/matter/${result.matterId}`;
    } else {
      window.location.href = `/matter/${result.matterId}/documents/${result.id}`;
    }
  }, []);

  // Clear search
  const handleClear = useCallback(() => {
    setQuery('');
    setResults([]);
    setError(null);
    inputRef.current?.focus();
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        inputRef.current?.blur();
      }
    },
    []
  );

  // Open popover when typing
  useEffect(() => {
    if (query.trim()) {
      setIsOpen(true);
    }
  }, [query]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const showResults = results.length > 0 && !error;
  const showEmpty = !isLoading && !error && query.trim().length >= 2 && results.length === 0;
  const showError = !isLoading && error !== null;

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverAnchor asChild>
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            type="search"
            placeholder="Search all matters..."
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => query.trim() && setIsOpen(true)}
            className="pl-9 pr-8"
            aria-label="Search all matters"
            aria-expanded={isOpen}
            aria-haspopup="listbox"
          />
          {query && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 h-6 w-6 -translate-y-1/2"
              onClick={handleClear}
              aria-label="Clear search"
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      </PopoverAnchor>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-2"
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {isLoading && (
          <div className="py-4 text-center text-sm text-muted-foreground">Searching...</div>
        )}
        {showEmpty && (
          <div className="py-4 text-center text-sm text-muted-foreground">
            No results found for &quot;{query}&quot;
          </div>
        )}
        {showError && (
          <div className="flex flex-col items-center gap-2 py-4">
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              <span>Search failed</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetry}
              className="flex items-center gap-1"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </Button>
          </div>
        )}
        {showResults && (
          <div className="space-y-1" role="listbox">
            {results.map((result) => (
              <SearchResultItem key={result.id} result={result} onSelect={handleResultSelect} />
            ))}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
