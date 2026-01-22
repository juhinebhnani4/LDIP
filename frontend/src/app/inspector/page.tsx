'use client';

/**
 * Inspector/Debug Page
 *
 * Admin page for testing and debugging the RAG search pipeline.
 * Shows detailed timing, scoring, and result information.
 *
 * Story: RAG Production Gaps - Feature 3: Inspector Mode
 */

import { useState } from 'react';
import { ArrowLeft, Search, Bug, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { InlineDebugInfo } from '@/components/features/inspector';
import { useInspector } from '@/hooks/useInspector';
import { useSession } from '@/hooks/useAuth';
import type { SearchDebugInfo } from '@/types/inspector';

export default function InspectorPage() {
  const { session } = useSession();
  const { searchWithDebug, inspectorEnabled } = useInspector();

  const [matterId, setMatterId] = useState('');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(20);
  const [bm25Weight, setBm25Weight] = useState(1.0);
  const [semanticWeight, setSemanticWeight] = useState(1.0);
  const [rerank, setRerank] = useState(true);
  const [rerankTopN, setRerankTopN] = useState(5);
  const [expandAliases, setExpandAliases] = useState(true);

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Array<Record<string, unknown>>>([]);
  const [debugInfo, setDebugInfo] = useState<SearchDebugInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!matterId || !query || !session?.access_token) {
      setError('Please enter Matter ID and Query');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await searchWithDebug(
        matterId,
        query,
        session.access_token,
        {
          limit,
          bm25Weight,
          semanticWeight,
          rerank,
          rerankTopN,
          expandAliases,
        }
      );

      if (result) {
        setResults(result.data);
        setDebugInfo(result.debug);
      } else {
        setError('Search failed. Check console for details.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (!inspectorEnabled) {
    return (
      <div className="container max-w-4xl py-6 px-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bug className="size-5" />
              Inspector Mode Disabled
            </CardTitle>
            <CardDescription>
              Inspector mode is disabled on the server. Set INSPECTOR_ENABLED=true in the backend configuration to enable.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="container max-w-5xl py-6 px-4 sm:px-6">
      {/* Header */}
      <div className="mb-8">
        <Button variant="ghost" size="sm" asChild className="mb-4 -ml-2">
          <Link href="/">
            <ArrowLeft className="size-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-3">
          <Bug className="size-7" />
          RAG Pipeline Inspector
        </h1>
        <p className="text-muted-foreground mt-1">
          Debug and analyze search behavior with detailed timing and scoring information.
        </p>
      </div>

      {/* Search Form */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Search Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4">
            {/* Matter ID and Query */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="matterId">Matter ID</Label>
                <Input
                  id="matterId"
                  value={matterId}
                  onChange={(e) => setMatterId(e.target.value)}
                  placeholder="Enter matter UUID"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="query">Search Query</Label>
                <Input
                  id="query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter search query"
                />
              </div>
            </div>

            {/* Weights and limits */}
            <div className="grid sm:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="limit">Limit</Label>
                <Input
                  id="limit"
                  type="number"
                  min={1}
                  max={100}
                  value={limit}
                  onChange={(e) => setLimit(parseInt(e.target.value) || 20)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bm25Weight">BM25 Weight</Label>
                <Input
                  id="bm25Weight"
                  type="number"
                  step={0.1}
                  min={0}
                  max={2}
                  value={bm25Weight}
                  onChange={(e) => setBm25Weight(parseFloat(e.target.value) || 1.0)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="semanticWeight">Semantic Weight</Label>
                <Input
                  id="semanticWeight"
                  type="number"
                  step={0.1}
                  min={0}
                  max={2}
                  value={semanticWeight}
                  onChange={(e) => setSemanticWeight(parseFloat(e.target.value) || 1.0)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rerankTopN">Rerank Top N</Label>
                <Input
                  id="rerankTopN"
                  type="number"
                  min={1}
                  max={20}
                  value={rerankTopN}
                  onChange={(e) => setRerankTopN(parseInt(e.target.value) || 5)}
                />
              </div>
            </div>

            {/* Options */}
            <div className="flex items-center gap-6">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="rerank"
                  checked={rerank}
                  onCheckedChange={(checked) => setRerank(checked === true)}
                />
                <Label htmlFor="rerank" className="font-normal">
                  Enable Reranking
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="expandAliases"
                  checked={expandAliases}
                  onCheckedChange={(checked) => setExpandAliases(checked === true)}
                />
                <Label htmlFor="expandAliases" className="font-normal">
                  Expand Aliases
                </Label>
              </div>
            </div>

            {/* Search Button */}
            <div className="flex justify-end">
              <Button onClick={handleSearch} disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="mr-2 h-4 w-4" />
                    Search with Debug
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Card className="mb-6 border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Debug Info */}
      {debugInfo && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Debug Information</CardTitle>
          </CardHeader>
          <CardContent>
            <InlineDebugInfo debugInfo={debugInfo} className="border-0 bg-transparent" />
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Results ({results.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {results.map((result, index) => (
                <div key={result.id as string} className="rounded-lg border p-4">
                  <div className="flex items-start justify-between mb-2">
                    <span className="font-medium">#{index + 1}</span>
                    <div className="flex gap-2 text-xs text-muted-foreground">
                      {typeof result.bm25_rank === 'number' && (
                        <span>BM25: #{result.bm25_rank}</span>
                      )}
                      {typeof result.semantic_rank === 'number' && (
                        <span>Semantic: #{result.semantic_rank}</span>
                      )}
                      <span>RRF: {(result.rrf_score as number)?.toFixed(4)}</span>
                      {typeof result.relevance_score === 'number' && (
                        <span className="font-medium text-green-600">
                          Rerank: {(result.relevance_score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {String(result.content)}
                  </p>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Page: {result.page_number ? String(result.page_number) : 'N/A'} | Tokens: {String(result.token_count)}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
