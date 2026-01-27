-- Story 1.2: Add LLM Detection for Suspicious Documents
-- Adds injection_risk column to documents table for prompt injection detection

-- Add injection_risk column to documents table
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS injection_risk TEXT DEFAULT 'none'
    CHECK (injection_risk IN ('none', 'low', 'medium', 'high'));

-- Add injection_scan_result column for detailed scan results (JSONB)
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS injection_scan_result JSONB DEFAULT NULL;

-- Add index for filtering by injection risk
CREATE INDEX IF NOT EXISTS idx_documents_injection_risk
ON documents (injection_risk)
WHERE injection_risk != 'none';

-- Add index for finding high-risk documents requiring review
CREATE INDEX IF NOT EXISTS idx_documents_high_injection_risk
ON documents (matter_id, injection_risk)
WHERE injection_risk = 'high';

-- Comment on columns for documentation
COMMENT ON COLUMN documents.injection_risk IS 'Prompt injection risk level: none, low, medium, high (Story 1.2)';
COMMENT ON COLUMN documents.injection_scan_result IS 'Detailed injection scan results from LLM detection (Story 1.2)';
