'use client';

/**
 * Admin Queue Status API Client
 *
 * Story 5.6: Queue Depth Visibility Dashboard
 *
 * API functions for admin-only queue depth monitoring.
 * Provides endpoints for:
 * - Getting current queue depths and metrics
 * - Health check for queue monitoring system
 *
 * Note: These operations require admin permissions.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export type QueueTrend = 'increasing' | 'decreasing' | 'stable';

export interface QueueMetrics {
  queueName: string;
  pendingCount: number;
  activeCount: number;
  failedCount: number;
  completed24h: number;
  avgProcessingTimeMs: number;
  trend: QueueTrend;
  alertTriggered: boolean;
}

export interface QueueStatusData {
  queues: QueueMetrics[];
  totalPending: number;
  totalActive: number;
  activeWorkers: number;
  lastCheckedAt: string;
  alertThreshold: number;
  isHealthy: boolean;
}

export interface QueueStatusResponse {
  data: QueueStatusData;
}

export interface QueueHealthData {
  status: 'healthy' | 'degraded' | 'unhealthy';
  redisConnected: boolean;
  workerCount: number;
  lastCheckedAt: string;
  error?: string;
}

export interface QueueHealthResponse {
  data: QueueHealthData;
}

// =============================================================================
// Response Transformers (Runtime type validation)
// =============================================================================

/** Safely parse a number with fallback */
function toNumber(value: unknown, fallback: number = 0): number {
  if (typeof value === 'number' && !Number.isNaN(value)) return value;
  if (typeof value === 'string') {
    const parsed = parseFloat(value);
    return Number.isNaN(parsed) ? fallback : parsed;
  }
  return fallback;
}

/** Safely parse a string with fallback */
function toString(value: unknown, fallback: string = ''): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return fallback;
  return String(value);
}

/** Safely parse a boolean with fallback */
function toBoolean(value: unknown, fallback: boolean = false): boolean {
  if (typeof value === 'boolean') return value;
  if (value === 'true') return true;
  if (value === 'false') return false;
  return fallback;
}

/** Safely parse trend enum */
function toTrend(value: unknown): QueueTrend {
  if (value === 'increasing' || value === 'decreasing' || value === 'stable') {
    return value;
  }
  return 'stable';
}

/** Safely parse health status enum */
function toHealthStatus(value: unknown): 'healthy' | 'degraded' | 'unhealthy' {
  if (value === 'healthy' || value === 'degraded' || value === 'unhealthy') {
    return value;
  }
  return 'unhealthy';
}

function transformQueueMetrics(data: Record<string, unknown>): QueueMetrics {
  return {
    queueName: toString(data.queueName ?? data.queue_name, 'unknown'),
    pendingCount: toNumber(data.pendingCount ?? data.pending_count),
    activeCount: toNumber(data.activeCount ?? data.active_count),
    failedCount: toNumber(data.failedCount ?? data.failed_count),
    completed24h: toNumber(data.completed24h ?? data.completed_24h),
    avgProcessingTimeMs: toNumber(data.avgProcessingTimeMs ?? data.avg_processing_time_ms),
    trend: toTrend(data.trend),
    alertTriggered: toBoolean(data.alertTriggered ?? data.alert_triggered),
  };
}

function transformQueueStatusData(data: Record<string, unknown>): QueueStatusData {
  const queues = (data.queues as Array<Record<string, unknown>> ?? []).map(transformQueueMetrics);

  return {
    queues,
    totalPending: toNumber(data.totalPending ?? data.total_pending),
    totalActive: toNumber(data.totalActive ?? data.total_active),
    activeWorkers: toNumber(data.activeWorkers ?? data.active_workers),
    lastCheckedAt: toString(data.lastCheckedAt ?? data.last_checked_at, new Date().toISOString()),
    alertThreshold: toNumber(data.alertThreshold ?? data.alert_threshold, 100),
    isHealthy: toBoolean(data.isHealthy ?? data.is_healthy, true),
  };
}

function transformQueueHealthData(data: Record<string, unknown>): QueueHealthData {
  return {
    status: toHealthStatus(data.status),
    redisConnected: toBoolean(data.redisConnected ?? data.redis_connected),
    workerCount: toNumber(data.workerCount ?? data.worker_count),
    lastCheckedAt: toString(data.lastCheckedAt ?? data.last_checked_at, new Date().toISOString()),
    error: data.error ? toString(data.error) : undefined,
  };
}

// =============================================================================
// Admin Queue API
// =============================================================================

/**
 * Get current queue status for all queues.
 *
 * @returns Queue status data with depths, metrics, and health status
 */
export async function getQueueStatus(): Promise<QueueStatusData> {
  const response = await api.get<{ data: Record<string, unknown> }>(
    '/api/admin/queue-status'
  );

  return transformQueueStatusData(response.data);
}

/**
 * Check queue monitoring system health.
 *
 * @returns Health check data with Redis and worker status
 */
export async function getQueueHealth(): Promise<QueueHealthData> {
  const response = await api.get<{ data: Record<string, unknown> }>(
    '/api/admin/queue-status/health'
  );

  return transformQueueHealthData(response.data);
}

// =============================================================================
// Exported API Object
// =============================================================================

export const adminQueueApi = {
  getQueueStatus,
  getQueueHealth,
};
