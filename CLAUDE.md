# CLAUDE.md - Project Configuration

## Engineering Philosophy

When fixing bugs or making architectural decisions, follow these principles:

1. **No band-aid fixes.** Every code change should be a long-term solution, not a quick patch. If a proper fix requires deeper work, do the deeper work.
2. **Research before implementing.** Explore all viable approaches, study how the industry solves the same problem (Unstructured.io, LangChain, LlamaIndex, Docling internals, etc.), and choose the approach that best fits jaanch's architecture.
3. **Future-ready design.** Code should accommodate foreseeable growth — new document types, new embedding providers, new pipeline stages — without requiring rewrites. Prefer extensible patterns over hardcoded solutions.
4. **Understand before changing.** Read the full call chain. Trace data flow end-to-end. Identify all callers and edge cases. Never modify code you haven't fully understood.
5. **Fix root causes, not symptoms.** If a table's text is missing from chunks, don't just add a fallback — find WHY it's missing (e.g., a type mismatch in extraction) and fix that. Fallbacks are safety nets, not solutions.

## Database Schema Discipline

**NEVER guess column names.** Before writing ANY Supabase query (.select(), .eq(), .in_(), .order(), etc.),
read the actual migration file to verify the exact column names. Common mistakes:

- `chunks` table PK is `id`, NOT `chunk_id`
- `chunks.parent_chunk_id`, NOT `parent_id`
- `chunks.text_start_offset` / `text_end_offset`, NOT `char_start` / `char_end`

**Migration files are the source of truth**, not comments, not spec docs, not variable names.
When in doubt, check `supabase/migrations/` before writing a query.

### Schema verification checklist (before any new DB query)
1. Find the CREATE TABLE migration for the table
2. Find any ALTER TABLE migrations that add columns
3. Confirm every column name in your .select() / .eq() / .in_() actually exists
4. Never trust comments like "References X.column" — verify the target table directly

## Deployment

**IMPORTANT**: When deploying, always deploy ALL services that have changes. Run commands from the repo root.

### Railway (Backend) — deploy BOTH services
- **Project**: trustworthy-passion
- **API service**: `railway up -s LDIP` (from repo root)
- **Worker service**: `railway up -s ldip-worker` (from repo root)
- **API URL**: jaanch-ai.up.railway.app
- **Always deploy both API and worker together** — they share the same codebase and must stay in sync.

### Vercel (Frontend)
- **Project**: ldip
- **Deploy command**: `cd frontend && vercel --prod`
- **Production URL**: https://www.jaanch-ai.in

### Full Deploy Sequence
When backend changes are involved, deploy everything:
```bash
# 1. Backend API (from repo root)
railway up -s LDIP
# 2. Backend Worker (from repo root)
railway up -s ldip-worker
# 3. Frontend (if frontend changes too)
cd frontend && vercel --prod
```
