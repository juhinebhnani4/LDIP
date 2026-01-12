-- Add CHECK constraint for entity_type to enforce valid values
-- This addresses the data integrity issue where entity_type was TEXT without validation

-- Add CHECK constraint to identity_nodes table
ALTER TABLE public.identity_nodes
ADD CONSTRAINT identity_nodes_entity_type_check
CHECK (entity_type IN ('PERSON', 'ORG', 'INSTITUTION', 'ASSET'));

-- Add CHECK constraint to identity_edges for relationship_type
ALTER TABLE public.identity_edges
ADD CONSTRAINT identity_edges_relationship_type_check
CHECK (relationship_type IN ('ALIAS_OF', 'HAS_ROLE', 'RELATED_TO'));

COMMENT ON CONSTRAINT identity_nodes_entity_type_check ON public.identity_nodes
IS 'Enforces valid entity types: PERSON, ORG, INSTITUTION, ASSET';

COMMENT ON CONSTRAINT identity_edges_relationship_type_check ON public.identity_edges
IS 'Enforces valid relationship types: ALIAS_OF, HAS_ROLE, RELATED_TO';
