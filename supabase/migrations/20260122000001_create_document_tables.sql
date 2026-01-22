-- Migration: Create document_tables for table extraction
-- Story: RAG Production Gaps - Feature 1: Table Extraction
-- Description: Stores tables extracted from documents using Docling

-- Create document_tables table
CREATE TABLE IF NOT EXISTS document_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    table_index INTEGER NOT NULL,
    page_number INTEGER,
    markdown_content TEXT NOT NULL,
    json_content JSONB,
    row_count INTEGER NOT NULL DEFAULT 0,
    col_count INTEGER NOT NULL DEFAULT 0,
    confidence FLOAT NOT NULL DEFAULT 0.9,
    bounding_box JSONB,
    caption TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure unique table per document
    CONSTRAINT unique_document_table UNIQUE (document_id, table_index)
);

-- Add table comment
COMMENT ON TABLE document_tables IS 'Tables extracted from documents using Docling for improved RAG retrieval';
COMMENT ON COLUMN document_tables.markdown_content IS 'Table content in Markdown format for LLM consumption';
COMMENT ON COLUMN document_tables.json_content IS 'Optional JSON representation of table data (list of row dicts)';
COMMENT ON COLUMN document_tables.bounding_box IS 'Location in document for citation highlighting (page, x, y, width, height)';
COMMENT ON COLUMN document_tables.confidence IS 'Extraction confidence score from Docling (0.0-1.0)';

-- Enable RLS
ALTER TABLE document_tables ENABLE ROW LEVEL SECURITY;

-- RLS policy: Users can only access tables in their matters
-- Uses the same pattern as other matter-scoped tables
CREATE POLICY "Users access own matter tables"
ON document_tables FOR ALL
USING (
    matter_id IN (
        SELECT matter_id FROM matter_attorneys
        WHERE user_id = auth.uid()
    )
);

-- Service role bypass for backend operations
CREATE POLICY "Service role full access to document_tables"
ON document_tables FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Indexes for common queries
CREATE INDEX idx_document_tables_document ON document_tables(document_id);
CREATE INDEX idx_document_tables_matter ON document_tables(matter_id);
CREATE INDEX idx_document_tables_page ON document_tables(document_id, page_number);

-- Index for confidence filtering
CREATE INDEX idx_document_tables_confidence ON document_tables(confidence)
WHERE confidence < 0.7;

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_document_tables_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER document_tables_updated_at
    BEFORE UPDATE ON document_tables
    FOR EACH ROW
    EXECUTE FUNCTION update_document_tables_updated_at();
