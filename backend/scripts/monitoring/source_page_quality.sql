-- Data Quality Monitoring Queries: Source Page Linkage
-- Run these periodically to detect data quality issues before users report them
-- Created: 2026-01-24

-- ============================================================================
-- 1. TIMELINE EVENTS: Check for high % of NULL source_page
-- Alert if > 30% of events in a matter have NULL source_page
-- ============================================================================
SELECT
    m.title as matter_title,
    e.matter_id,
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE e.source_page IS NULL) as null_pages,
    ROUND(
        COUNT(*) FILTER (WHERE e.source_page IS NULL)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    ) as null_pct
FROM events e
JOIN matters m ON e.matter_id = m.id
WHERE e.created_at > NOW() - INTERVAL '7 days'
GROUP BY e.matter_id, m.title
HAVING COUNT(*) FILTER (WHERE e.source_page IS NULL)::numeric
       / NULLIF(COUNT(*), 0) > 0.3
ORDER BY null_pct DESC;


-- ============================================================================
-- 2. CITATIONS: Check for suspicious page 1 concentration
-- Alert if > 50% of citations go to page 1 (likely fallback, not actual data)
-- ============================================================================
SELECT
    m.title as matter_title,
    c.matter_id,
    COUNT(*) as total_citations,
    COUNT(*) FILTER (WHERE c.source_page = 1) as page_1_count,
    COUNT(*) FILTER (WHERE c.source_page IS NULL) as null_page_count,
    ROUND(
        COUNT(*) FILTER (WHERE c.source_page = 1)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    ) as page_1_pct
FROM citations c
JOIN matters m ON c.matter_id = m.id
WHERE c.created_at > NOW() - INTERVAL '7 days'
GROUP BY c.matter_id, m.title
HAVING COUNT(*) > 10
   AND COUNT(*) FILTER (WHERE c.source_page = 1)::numeric
       / NULLIF(COUNT(*), 0) > 0.5
ORDER BY page_1_pct DESC;


-- ============================================================================
-- 3. CHUNKS: Check for missing page_number (upstream issue)
-- Alert if > 20% of chunks lack page_number (will cascade to all engines)
-- ============================================================================
SELECT
    m.title as matter_title,
    d.matter_id,
    COUNT(*) as total_chunks,
    COUNT(*) FILTER (WHERE c.page_number IS NULL) as null_pages,
    ROUND(
        COUNT(*) FILTER (WHERE c.page_number IS NULL)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    ) as null_pct
FROM chunks c
JOIN documents d ON c.document_id = d.id
JOIN matters m ON d.matter_id = m.id
WHERE c.created_at > NOW() - INTERVAL '7 days'
GROUP BY d.matter_id, m.title
HAVING COUNT(*) FILTER (WHERE c.page_number IS NULL)::numeric
       / NULLIF(COUNT(*), 0) > 0.2
ORDER BY null_pct DESC;


-- ============================================================================
-- 4. ENTITIES (MIG): Check for missing page_number
-- Alert if > 40% of entity mentions lack page_number
-- ============================================================================
SELECT
    m.title as matter_title,
    me.matter_id,
    COUNT(*) as total_mentions,
    COUNT(*) FILTER (WHERE me.page_number IS NULL) as null_pages,
    ROUND(
        COUNT(*) FILTER (WHERE me.page_number IS NULL)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    ) as null_pct
FROM mig_entity_mentions me
JOIN matters m ON me.matter_id = m.id
WHERE me.created_at > NOW() - INTERVAL '7 days'
GROUP BY me.matter_id, m.title
HAVING COUNT(*) FILTER (WHERE me.page_number IS NULL)::numeric
       / NULLIF(COUNT(*), 0) > 0.4
ORDER BY null_pct DESC;


-- ============================================================================
-- 5. OVERALL HEALTH: Summary across all engines for a specific matter
-- Replace 'YOUR_MATTER_ID' with actual UUID
-- ============================================================================
WITH matter_health AS (
    SELECT 'YOUR_MATTER_ID'::uuid as matter_id  -- Replace with actual matter ID
)
SELECT
    'events' as table_name,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE source_page IS NULL) as null_count,
    ROUND(COUNT(*) FILTER (WHERE source_page IS NULL)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as null_pct
FROM events, matter_health
WHERE events.matter_id = matter_health.matter_id

UNION ALL

SELECT
    'citations' as table_name,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE source_page IS NULL OR source_page = 1) as suspicious_count,
    ROUND(COUNT(*) FILTER (WHERE source_page IS NULL OR source_page = 1)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as suspicious_pct
FROM citations, matter_health
WHERE citations.matter_id = matter_health.matter_id

UNION ALL

SELECT
    'chunks' as table_name,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE page_number IS NULL) as null_count,
    ROUND(COUNT(*) FILTER (WHERE page_number IS NULL)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as null_pct
FROM chunks c
JOIN documents d ON c.document_id = d.id
JOIN matter_health mh ON d.matter_id = mh.matter_id;


-- ============================================================================
-- 6. RECENT DOCUMENTS: Check bbox linking success rate
-- Identifies documents where chunk-to-bbox linking may have failed
-- ============================================================================
SELECT
    d.filename,
    d.id as document_id,
    d.matter_id,
    COUNT(c.id) as total_chunks,
    COUNT(c.id) FILTER (WHERE c.page_number IS NOT NULL) as chunks_with_page,
    COUNT(c.id) FILTER (WHERE c.bbox_ids IS NOT NULL AND array_length(c.bbox_ids, 1) > 0) as chunks_with_bbox,
    ROUND(
        COUNT(c.id) FILTER (WHERE c.page_number IS NOT NULL)::numeric
        / NULLIF(COUNT(c.id), 0) * 100, 1
    ) as page_coverage_pct
FROM documents d
LEFT JOIN chunks c ON d.id = c.document_id
WHERE d.created_at > NOW() - INTERVAL '7 days'
  AND d.status = 'processed'
GROUP BY d.id, d.filename, d.matter_id
HAVING COUNT(c.id) > 0
   AND COUNT(c.id) FILTER (WHERE c.page_number IS NOT NULL)::numeric
       / NULLIF(COUNT(c.id), 0) < 0.9
ORDER BY page_coverage_pct ASC;
