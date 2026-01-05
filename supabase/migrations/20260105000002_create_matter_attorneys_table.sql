-- Create matter_attorneys table for role-per-matter model
-- This implements FR29 Authorization with Owner/Editor/Viewer roles

-- =============================================================================
-- TABLE: matter_attorneys - Role assignments for matters
-- =============================================================================

CREATE TABLE public.matter_attorneys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
  invited_by uuid REFERENCES auth.users(id),
  invited_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now(),

  -- One role per user per matter
  UNIQUE(matter_id, user_id)
);

-- Performance indexes
CREATE INDEX idx_matter_attorneys_matter_id ON public.matter_attorneys(matter_id);
CREATE INDEX idx_matter_attorneys_user_id ON public.matter_attorneys(user_id);
CREATE INDEX idx_matter_attorneys_role ON public.matter_attorneys(role);

-- Comments
COMMENT ON TABLE public.matter_attorneys IS 'Role assignments linking users to matters with specific permissions';
COMMENT ON COLUMN public.matter_attorneys.matter_id IS 'FK to matters table';
COMMENT ON COLUMN public.matter_attorneys.user_id IS 'FK to auth.users table';
COMMENT ON COLUMN public.matter_attorneys.role IS 'User role on this matter: owner, editor, or viewer';
COMMENT ON COLUMN public.matter_attorneys.invited_by IS 'User who invited this member (NULL for creator)';
COMMENT ON COLUMN public.matter_attorneys.invited_at IS 'When the invitation was sent/created';

-- =============================================================================
-- RLS POLICIES: matter_attorneys table
-- =============================================================================

ALTER TABLE public.matter_attorneys ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can view their own memberships
CREATE POLICY "Users can view own memberships"
ON public.matter_attorneys FOR SELECT
USING (user_id = auth.uid());

-- Policy 2: Users can view all members of matters they belong to
CREATE POLICY "Users can view matter members"
ON public.matter_attorneys FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 3: Owners can insert new members to their matters
CREATE POLICY "Owners can insert members"
ON public.matter_attorneys FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_attorneys.matter_id
    AND ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
  -- Also allow the auto-assign trigger (which runs as SECURITY DEFINER)
  OR (
    -- Allow inserting self as owner when creating a matter
    user_id = auth.uid() AND role = 'owner'
  )
);

-- Policy 4: Owners can update member roles (but not their own owner role)
CREATE POLICY "Owners can update member roles"
ON public.matter_attorneys FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_attorneys.matter_id
    AND ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
)
WITH CHECK (
  -- Cannot change own owner role to something else
  NOT (user_id = auth.uid() AND role != 'owner')
);

-- Policy 5: Owners can delete members (but not themselves)
CREATE POLICY "Owners can delete members"
ON public.matter_attorneys FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_attorneys.matter_id
    AND ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
  -- Cannot delete self
  AND user_id != auth.uid()
);

-- =============================================================================
-- RLS POLICIES: matters table (depends on matter_attorneys)
-- =============================================================================

-- Policy 1: Users can SELECT matters where they have any role
CREATE POLICY "Users can view own matters"
ON public.matters FOR SELECT
USING (
  id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
  )
  AND deleted_at IS NULL
);

-- Policy 2: Authenticated users can INSERT new matters
-- (Creator becomes owner via trigger below)
CREATE POLICY "Authenticated users can create matters"
ON public.matters FOR INSERT
WITH CHECK (auth.uid() IS NOT NULL);

-- Policy 3: Editors and Owners can UPDATE matter details
CREATE POLICY "Editors and Owners can update matters"
ON public.matters FOR UPDATE
USING (
  id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
    AND role IN ('owner', 'editor')
  )
  AND deleted_at IS NULL
);

-- Policy 4: Only Owners can DELETE (soft-delete) matters
CREATE POLICY "Only Owners can delete matters"
ON public.matters FOR DELETE
USING (
  id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
    AND role = 'owner'
  )
);

-- =============================================================================
-- TRIGGER: Auto-assign owner on matter creation
-- =============================================================================

CREATE OR REPLACE FUNCTION public.auto_assign_matter_owner()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.matter_attorneys (matter_id, user_id, role, invited_by)
  VALUES (NEW.id, auth.uid(), 'owner', auth.uid());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_matter_created
  AFTER INSERT ON public.matters
  FOR EACH ROW
  EXECUTE FUNCTION public.auto_assign_matter_owner();

-- Comment
COMMENT ON FUNCTION public.auto_assign_matter_owner() IS 'Automatically assigns the creating user as owner of a new matter';
