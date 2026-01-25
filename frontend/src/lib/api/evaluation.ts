'use client';

/**
 * Evaluation API Client
 *
 * API functions for RAG evaluation framework and golden dataset management.
 * Provides endpoints for:
 * - Evaluating QA pairs using RAGAS metrics
 * - Managing golden dataset items
 * - Retrieving historical evaluation results
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface EvaluationScores {
  faithfulness: number | null;
  answerRelevancy: number | null;
  contextRecall: number | null;
}

export interface EvaluationResult {
  scores: EvaluationScores;
  overallScore: number;
  evaluatedAt: string;
}

export interface EvaluateRequest {
  question: string;
  answer: string;
  contexts: string[];
  groundTruth?: string;
  saveResult?: boolean;
}

export interface BatchEvaluateRequest {
  tags?: string[];
}

export interface GoldenDatasetItem {
  id: string;
  matterId: string;
  question: string;
  expectedAnswer: string;
  relevantChunkIds: string[];
  tags: string[];
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface AddGoldenItemRequest {
  question: string;
  expectedAnswer: string;
  relevantChunkIds?: string[];
  tags?: string[];
}

export interface UpdateGoldenItemRequest {
  question?: string;
  expectedAnswer?: string;
  relevantChunkIds?: string[];
  tags?: string[];
}

export interface EvaluationResultRecord {
  id: string;
  matterId: string;
  question: string;
  answer: string;
  contexts: string[];
  faithfulness: number | null;
  answerRelevancy: number | null;
  contextRecall: number | null;
  overallScore: number;
  triggeredBy: 'manual' | 'auto' | 'batch';
  evaluatedAt: string;
}

export interface PaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

// =============================================================================
// Response Transformers
// =============================================================================

function transformGoldenItem(item: Record<string, unknown>): GoldenDatasetItem {
  return {
    id: item.id as string,
    matterId: (item.matter_id ?? item.matterId) as string,
    question: item.question as string,
    expectedAnswer: (item.expected_answer ?? item.expectedAnswer) as string,
    relevantChunkIds: (item.relevant_chunk_ids ?? item.relevantChunkIds ?? []) as string[],
    tags: (item.tags ?? []) as string[],
    createdBy: (item.created_by ?? item.createdBy) as string,
    createdAt: (item.created_at ?? item.createdAt) as string,
    updatedAt: (item.updated_at ?? item.updatedAt) as string,
  };
}

function transformEvaluationResult(item: Record<string, unknown>): EvaluationResultRecord {
  return {
    id: item.id as string,
    matterId: (item.matter_id ?? item.matterId) as string,
    question: item.question as string,
    answer: item.answer as string,
    contexts: (item.contexts ?? []) as string[],
    faithfulness: item.faithfulness as number | null,
    answerRelevancy: (item.answer_relevancy ?? item.answerRelevancy) as number | null,
    contextRecall: (item.context_recall ?? item.contextRecall) as number | null,
    overallScore: (item.overall_score ?? item.overallScore) as number,
    triggeredBy: (item.triggered_by ?? item.triggeredBy) as 'manual' | 'auto' | 'batch',
    evaluatedAt: (item.evaluated_at ?? item.evaluatedAt) as string,
  };
}

// =============================================================================
// Evaluation API
// =============================================================================

/**
 * Evaluate a single QA pair using RAGAS metrics.
 *
 * @param matterId - Matter UUID
 * @param request - Evaluation request with question, answer, contexts
 * @returns Evaluation result with scores
 */
export async function evaluateQAPair(
  matterId: string,
  request: EvaluateRequest
): Promise<EvaluationResult> {
  const response = await api.post<{ data: Record<string, unknown> }>(
    `/api/matters/${matterId}/evaluation/evaluate`,
    {
      question: request.question,
      answer: request.answer,
      contexts: request.contexts,
      ground_truth: request.groundTruth,
      save_result: request.saveResult,
    }
  );

  const data = response.data;
  const scores = data.scores as Record<string, unknown>;

  return {
    scores: {
      faithfulness: scores.faithfulness as number | null,
      answerRelevancy: (scores.answer_relevancy ?? scores.answerRelevancy) as number | null,
      contextRecall: (scores.context_recall ?? scores.contextRecall) as number | null,
    },
    overallScore: (data.overall_score ?? data.overallScore) as number,
    evaluatedAt: (data.evaluated_at ?? data.evaluatedAt ?? new Date().toISOString()) as string,
  };
}

/**
 * Trigger batch evaluation of golden dataset items.
 *
 * @param matterId - Matter UUID
 * @param request - Optional tags to filter items
 * @returns Task ID and status
 */
export async function triggerBatchEvaluation(
  matterId: string,
  request?: BatchEvaluateRequest
): Promise<{ taskId: string; status: string; message: string }> {
  const response = await api.post<{ data: Record<string, unknown> }>(
    `/api/matters/${matterId}/evaluation/evaluate/batch`,
    { tags: request?.tags }
  );

  return {
    taskId: (response.data.task_id ?? response.data.taskId) as string,
    status: response.data.status as string,
    message: response.data.message as string,
  };
}

/**
 * Get historical evaluation results.
 *
 * @param matterId - Matter UUID
 * @param options - Pagination and filter options
 * @returns Paginated evaluation results
 */
export async function getEvaluationResults(
  matterId: string,
  options?: {
    page?: number;
    perPage?: number;
    triggeredBy?: 'manual' | 'auto' | 'batch';
  }
): Promise<{ data: EvaluationResultRecord[]; meta: PaginationMeta }> {
  const params = new URLSearchParams();
  if (options?.page) params.set('page', String(options.page));
  if (options?.perPage) params.set('per_page', String(options.perPage));
  if (options?.triggeredBy) params.set('triggered_by', options.triggeredBy);

  const query = params.toString();
  const response = await api.get<{
    data: Record<string, unknown>[];
    meta: Record<string, unknown>;
  }>(`/api/matters/${matterId}/evaluation/results${query ? `?${query}` : ''}`);

  return {
    data: response.data.map(transformEvaluationResult),
    meta: {
      total: (response.meta.total ?? 0) as number,
      page: (response.meta.page ?? 1) as number,
      perPage: ((response.meta.per_page ?? response.meta.perPage) ?? 20) as number,
      totalPages: ((response.meta.total_pages ?? response.meta.totalPages) ?? 0) as number,
    },
  };
}

// =============================================================================
// Golden Dataset API
// =============================================================================

/**
 * Get golden dataset items for a matter.
 *
 * @param matterId - Matter UUID
 * @param options - Pagination and filter options
 * @returns Paginated golden dataset items
 */
export async function getGoldenDataset(
  matterId: string,
  options?: {
    page?: number;
    perPage?: number;
    tags?: string[];
  }
): Promise<{ data: GoldenDatasetItem[]; meta: PaginationMeta }> {
  const params = new URLSearchParams();
  if (options?.page) params.set('page', String(options.page));
  if (options?.perPage) params.set('per_page', String(options.perPage));
  if (options?.tags?.length) params.set('tags', options.tags.join(','));

  const query = params.toString();
  const response = await api.get<{
    data: Record<string, unknown>[];
    meta: Record<string, unknown>;
  }>(`/api/matters/${matterId}/evaluation/golden-dataset${query ? `?${query}` : ''}`);

  return {
    data: response.data.map(transformGoldenItem),
    meta: {
      total: (response.meta.total ?? 0) as number,
      page: (response.meta.page ?? 1) as number,
      perPage: ((response.meta.per_page ?? response.meta.perPage) ?? 20) as number,
      totalPages: ((response.meta.total_pages ?? response.meta.totalPages) ?? 0) as number,
    },
  };
}

/**
 * Add a QA pair to the golden dataset.
 *
 * @param matterId - Matter UUID
 * @param item - Golden item data
 * @returns Created golden dataset item
 */
export async function addGoldenItem(
  matterId: string,
  item: AddGoldenItemRequest
): Promise<GoldenDatasetItem> {
  const response = await api.post<{ data: Record<string, unknown> }>(
    `/api/matters/${matterId}/evaluation/golden-dataset`,
    {
      question: item.question,
      expected_answer: item.expectedAnswer,
      relevant_chunk_ids: item.relevantChunkIds,
      tags: item.tags,
    }
  );

  return transformGoldenItem(response.data);
}

/**
 * Get a specific golden dataset item.
 *
 * @param matterId - Matter UUID
 * @param itemId - Item UUID
 * @returns Golden dataset item
 */
export async function getGoldenItem(
  matterId: string,
  itemId: string
): Promise<GoldenDatasetItem> {
  const response = await api.get<{ data: Record<string, unknown> }>(
    `/api/matters/${matterId}/evaluation/golden-dataset/${itemId}`
  );

  return transformGoldenItem(response.data);
}

/**
 * Update a golden dataset item.
 *
 * @param matterId - Matter UUID
 * @param itemId - Item UUID
 * @param updates - Fields to update
 * @returns Updated golden dataset item
 */
export async function updateGoldenItem(
  matterId: string,
  itemId: string,
  updates: UpdateGoldenItemRequest
): Promise<GoldenDatasetItem> {
  const body: Record<string, unknown> = {};
  if (updates.question !== undefined) body.question = updates.question;
  if (updates.expectedAnswer !== undefined) body.expected_answer = updates.expectedAnswer;
  if (updates.relevantChunkIds !== undefined) body.relevant_chunk_ids = updates.relevantChunkIds;
  if (updates.tags !== undefined) body.tags = updates.tags;

  const response = await api.patch<{ data: Record<string, unknown> }>(
    `/api/matters/${matterId}/evaluation/golden-dataset/${itemId}`,
    body
  );

  return transformGoldenItem(response.data);
}

/**
 * Delete a golden dataset item.
 *
 * @param matterId - Matter UUID
 * @param itemId - Item UUID
 * @returns Deletion confirmation
 */
export async function deleteGoldenItem(
  matterId: string,
  itemId: string
): Promise<{ deleted: boolean; id: string }> {
  const response = await api.delete<{ data: { deleted: boolean; id: string } }>(
    `/api/matters/${matterId}/evaluation/golden-dataset/${itemId}`
  );

  return response.data;
}

// =============================================================================
// Exported API Object
// =============================================================================

export const evaluationApi = {
  // Evaluation
  evaluate: evaluateQAPair,
  triggerBatch: triggerBatchEvaluation,
  getResults: getEvaluationResults,

  // Golden Dataset
  getGoldenDataset,
  addGoldenItem,
  getGoldenItem,
  updateGoldenItem,
  deleteGoldenItem,
};
