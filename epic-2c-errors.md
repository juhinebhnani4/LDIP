# Code Review Findings: Forensic Deep Dive (Epic 2c)

**Review Status**: 🔴 **CRITICAL FAIL**
**Scope**: Epic 2c (MIG, Entity Extraction, Alias Resolution)

## 🚨 Critical Security & Integrity Vulnerabilities

### 1. Data Loss on Entity Merge (Cascading Deletes)
- **Severity**: **CRITICAL (Data Loss)**
- **Affected File**: `supabase/migrations/20260106000009_create_mig_tables.sql` (Function `merge_entities`)
- **Vulnerability**: The `merge_entities` function deletes the `p_merge_id` (merged entity) at the end of the transaction. The `entity_mentions` table takes a cascading delete from `identity_nodes` (`ON DELETE CASCADE`).
- **Impact**: All highlighting, bounding boxes, and mentions associated with the merged entity are **permanently deleted**.
- **Fix**: Before deleting `p_merge_id`, you must update `entity_mentions` to point to `p_keep_id`.
  ```sql
  UPDATE public.entity_mentions
  SET entity_id = p_keep_id
  WHERE entity_id = p_merge_id;
  ```

### 2. Cross-Matter Reference Injection (RLS Gap)
- **Severity**: **CRITICAL (Security)**
- **Affected File**: `supabase/migrations/20260112000001_create_entity_mentions_table.sql`
- **Vulnerability**: The RLS policy for `INSERT` on `entity_mentions` validates that the `entity_id` belongs to the user's matter. However, it **fails to validate** that the `document_id` also belongs to the *same* matter.
- **Exploit**: A malicious user (or compromised account) can insert a mention linking *their* entity to a `document_id` from a *different* matter (if they can guess/enumerate the UUID). This creates cross-matter data pollution and potentially leaks document existence.
- **Fix**: Add a check in the `WITH CHECK` clause ensuring `document_id` belongs to the same matter as `entity_id`.

---

## 🟡 Medium Issues

### 3. Namespace Ambiguity (Alias vs Entity)
- **Severity**: Medium
- **Affected File**: `backend/app/services/mig/graph.py` (`add_alias_to_entity`)
- **Impact**: The system allows adding an alias (e.g., "Bob") to an entity ("Robert") even if a separate canonical entity named "Bob" already exists in the same matter. This creates ambiguous resolution states where "Bob" resolves to two different nodes.
- **Fix**: Check for existing canonical entities matching the alias name before adding it; if found, prompt for a merge instead.

### 4. Performance Bottleneck (Listing Entities)
- **Severity**: Medium
- **Affected File**: `supabase/migrations/20260106000009_create_mig_tables.sql`
- **Impact**: The API `list_entities` sorts by `mention_count DESC`. While `mention_count` is indexed in `entity_mentions` (wait, no, it's a column on `identity_nodes`), there is no composite index on `(matter_id, mention_count DESC)`. For large matters with thousands of entities, this sort will be slow.
- **Fix**: Add `CREATE INDEX idx_identity_nodes_matter_mentions ON public.identity_nodes(matter_id, mention_count DESC);`.

### 5. Silent Data Truncation
- **Severity**: Low
- **Affected File**: `backend/app/services/mig/extractor.py`
- **Impact**: Text input > 30,000 characters is silently truncated. If a large document chunk is processed, entities at the end will be missed without any warning or error log indicating partial processing.
- **Fix**: Logging a warning is good (which is present), but for an ingestion pipeline, we should ideally process in chunks or error out rather than silently dropping data.

### 6. Transitive Closure Scope
- **Severity**: Low
- **Affected File**: `backend/app/services/mig/entity_resolver.py`
- **Impact**: `_apply_transitive_closure` only considers the *new* edges being created in the current batch. It does not look up existing edges in the database. If A=B exists in DB, and B=C is found, A=C will not be created unless all 3 are in the current batch.
