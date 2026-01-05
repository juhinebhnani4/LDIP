-- Create matters table for legal matters/cases
-- This is the core entity that attorneys work on

CREATE TABLE public.matters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'closed')),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  deleted_at timestamptz  -- Soft delete support
);

-- Enable Row Level Security
ALTER TABLE public.matters ENABLE ROW LEVEL SECURITY;

-- Note: RLS policies are defined in the next migration after matter_attorneys exists
-- This is because matter access is determined by membership in matter_attorneys

-- Create index on status for filtering
CREATE INDEX idx_matters_status ON public.matters(status) WHERE deleted_at IS NULL;

-- Create index on deleted_at for soft-delete queries
CREATE INDEX idx_matters_deleted_at ON public.matters(deleted_at);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on modification
CREATE TRIGGER set_matters_updated_at
  BEFORE UPDATE ON public.matters
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE public.matters IS 'Legal matters/cases that attorneys work on';
COMMENT ON COLUMN public.matters.id IS 'Unique identifier for the matter';
COMMENT ON COLUMN public.matters.title IS 'Matter title/name';
COMMENT ON COLUMN public.matters.description IS 'Optional description of the matter';
COMMENT ON COLUMN public.matters.status IS 'Matter status: active, archived, or closed';
COMMENT ON COLUMN public.matters.created_at IS 'Timestamp when matter was created';
COMMENT ON COLUMN public.matters.updated_at IS 'Timestamp when matter was last updated';
COMMENT ON COLUMN public.matters.deleted_at IS 'Soft delete timestamp (NULL = not deleted)';
