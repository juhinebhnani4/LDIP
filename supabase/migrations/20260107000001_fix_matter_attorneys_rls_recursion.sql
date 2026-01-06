-- Fix infinite recursion in matter_attorneys RLS policy
-- The original "Users can view matter members" policy caused infinite recursion
-- by querying matter_attorneys within its own USING clause.

-- Drop the problematic policy
DROP POLICY IF EXISTS "Users can view matter members" ON public.matter_attorneys;

-- The remaining policy "Users can view own memberships" is sufficient:
-- - Users see their own memberships (which includes the matter_id)
-- - Other policies on matters/documents use matter_attorneys correctly
-- - For viewing OTHER members of a matter, we use a function approach

-- Create a security definer function to check matter membership without recursion
CREATE OR REPLACE FUNCTION public.user_has_matter_access(check_matter_id uuid)
RETURNS boolean AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.matter_attorneys
    WHERE matter_id = check_matter_id
    AND user_id = auth.uid()
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION public.user_has_matter_access(uuid) IS 'Check if current user has any role on the specified matter. Used to avoid RLS recursion.';

-- New policy: View all members of matters you belong to (using function to avoid recursion)
CREATE POLICY "Users can view co-members via function"
ON public.matter_attorneys FOR SELECT
USING (
  public.user_has_matter_access(matter_id)
);
