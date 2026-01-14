'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Search, FileText, Briefcase, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverAnchor,
} from '@/components/ui/popover';

/** Search result item type */
interface SearchResult {
  id: string;
  type: 'matter' | 'document';
  title: string;
  matterId: string;
  matterTitle: string;
  matchedContent: string;
}

/** Mock search results for development */
function getMockSearchResults(query: string): SearchResult[] {
  if (!query.trim()) return [];

  const allResults: SearchResult[] = [
    {
      id: 'result-1',
      type: 'matter',
      title: 'Smith vs. Jones',
      matterId: 'matter-1',
      matterTitle: 'Smith vs. Jones',
      matchedContent: 'Contract dispute regarding property boundaries...',
    },
    {
      id: 'result-2',
      type: 'document',
      title: 'Contract_Agreement_2024.pdf',
      matterId: 'matter-1',
      matterTitle: 'Smith vs. Jones',
      matchedContent: '...the terms of the agreement state that...',
    },
    {
      id: 'result-3',
      type: 'matter',
      title: 'Acme Corp Acquisition',
      matterId: 'matter-2',
      matterTitle: 'Acme Corp Acquisition',
      matchedContent: 'Corporate acquisition and merger documentation...',
    },
    {
      id: 'result-4',
      type: 'document',
      title: 'Due_Diligence_Report.pdf',
      matterId: 'matter-2',
      matterTitle: 'Acme Corp Acquisition',
      matchedContent: '...financial analysis shows growth potential...',
    },
    {
      id: 'result-5',
      type: 'document',
      title: 'Evidence_Summary.docx',
      matterId: 'matter-1',
      matterTitle: 'Smith vs. Jones',
      matchedContent: '...witness testimony corroborates the claim...',
    },
  ];

  // Simple filtering based on query
  const lowerQuery = query.toLowerCase();
  return allResults.filter(
    (result) =>
      result.title.toLowerCase().includes(lowerQuery) ||
      result.matterTitle.toLowerCase().includes(lowerQuery) ||
      result.matchedContent.toLowerCase().includes(lowerQuery)
  );
}

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
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Debounced search function
  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      // TODO: Replace with actual API call when backend is available
      // const response = await fetch(`/api/search?q=${encodeURIComponent(searchQuery)}`);
      // const { data } = await response.json();

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 200));
      const searchResults = getMockSearchResults(searchQuery);
      setResults(searchResults);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

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

    // Navigate based on type
    if (result.type === 'matter') {
      window.location.href = `/matters/${result.matterId}`;
    } else {
      window.location.href = `/matters/${result.matterId}/documents/${result.id}`;
    }
  }, []);

  // Clear search
  const handleClear = useCallback(() => {
    setQuery('');
    setResults([]);
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

  const showResults = results.length > 0;
  const showEmpty = !isLoading && query.trim() && results.length === 0;

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
