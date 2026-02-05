# Supabase Egress Crisis - Research & Solutions

**Date:** 2026-01-29
**Status:** Service Restricted (18.27GB / 5GB = 365% cached egress usage)
**Reset Date:** February 2, 2026

## Current Situation Analysis

| Metric | Value | Limit | Status |
|--------|-------|-------|--------|
| Cached Egress | 18.27 GB | 5 GB | **365% - BLOCKED** |
| Uncached Egress | 2.84 GB | 5 GB | 57% - OK |
| Database Size | 179.22 MB | 500 MB | 38% - OK |
| Storage Size | 0.13 GB | 1 GB | 13% - OK |

### Biggest Tables (Egress Sources)
| Table | Size | Likely Egress Impact |
|-------|------|---------------------|
| bounding_boxes | 89 MB | HIGH (large JSONB data) |
| chunks | 31 MB | HIGH (text content) |
| entity_mentions | 8.7 MB | MEDIUM |
| events | 7.8 MB | MEDIUM |
| documents | 3.3 MB | LOW-MEDIUM |
| citations | 3.3 MB | LOW-MEDIUM |

---

## SOLUTION OPTIONS (Ranked by Feasibility)

### Option 1: QUICK HACKS (Immediate - No Migration)

#### A. Cloudflare Workers + KV Cache (FREE)
**How it works:** Put Cloudflare in front of Supabase to cache API responses at the edge.

**Setup:**
1. Create Cloudflare Worker that proxies Supabase requests
2. Cache responses in KV Storage (100,000 reads/day free)
3. Set cache TTL based on data freshness needs

**Example Worker:**
```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const cacheKey = new URL(request.url).pathname
  const cached = await SUPABASE_CACHE.get(cacheKey)

  if (cached) {
    return new Response(cached, { headers: { 'Content-Type': 'application/json' } })
  }

  const response = await fetch(request.url.replace('your-domain', 'supabase-url'))
  const data = await response.text()

  await SUPABASE_CACHE.put(cacheKey, data, { expirationTtl: 300 }) // 5 min cache
  return new Response(data, { headers: { 'Content-Type': 'application/json' } })
}
```

**Pros:** Free, immediate, no code changes needed
**Cons:** Only caches read requests, need to invalidate on writes

#### B. Frontend Caching with SWR/React Query
**Already using:** React Query with 5-minute stale time
**Quick fixes:**
- Increase stale times for static data
- Add localStorage persistence
- Reduce polling intervals (currently 5s in useDocumentStatus)

```typescript
// Change from 5s polling to 30s
const POLLING_INTERVAL_MS = 30000; // Was 5000
```

#### C. Browser Cache Headers
Set aggressive Cache-Control headers for static API responses:
```python
# In FastAPI responses
response.headers["Cache-Control"] = "public, max-age=3600"  # 1 hour
```

---

### Option 2: MOVE FILES TO AWS S3 (Medium Effort)

**Rationale:** Your 0.13 GB storage is serving 18+ GB egress. Files are being downloaded repeatedly.

#### Migration Steps:
1. **Create S3 Bucket** (AWS Free Tier: 5GB storage, 15GB/month data out)
2. **Migrate existing files:**
   ```bash
   aws s3 sync ./local-backup s3://your-bucket/
   ```
3. **Update storage_service.py:**
   ```python
   import boto3

   class S3StorageService:
       def __init__(self):
           self.s3 = boto3.client('s3',
               aws_access_key_id=settings.AWS_ACCESS_KEY,
               aws_secret_access_key=settings.AWS_SECRET_KEY
           )
           self.bucket = settings.S3_BUCKET

       def upload_file(self, file_content, path):
           self.s3.put_object(
               Bucket=self.bucket,
               Key=path,
               Body=file_content
           )
           return f"https://{self.bucket}.s3.amazonaws.com/{path}"

       def get_presigned_url(self, path, expires=3600):
           return self.s3.generate_presigned_url(
               'get_object',
               Params={'Bucket': self.bucket, 'Key': path},
               ExpiresIn=expires
           )
   ```

4. **Add CloudFront CDN** (Optional but recommended):
   - Free tier: 1TB/month data transfer
   - Automatic caching at edge locations

**Pros:** AWS free tier is generous, CloudFront caching, better for large files
**Cons:** Requires code changes, another service to manage

---

### Option 3: MIGRATE DATABASE TO NEON (Medium-High Effort)

**Neon Free Tier:**
- 0.5 GB storage
- 191.9 compute hours/month
- Auto-suspend after 5 min inactivity
- **Key benefit:** Serverless scaling, branching for dev/staging

#### Migration Steps:

1. **Export from Supabase:**
   ```bash
   pg_dump -Fc -v \
     -d postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres \
     --schema=public \
     -f supabase_dump.bak
   ```

2. **Import to Neon:**
   ```bash
   pg_restore \
     -d postgresql://[user]:[password]@[neon-host]/[database] \
     -v --no-owner --no-acl \
     supabase_dump.bak
   ```

3. **Update connection strings in .env:**
   ```env
   DATABASE_URL=postgresql://[user]:[password]@[neon-host]/[database]
   ```

4. **Auth Migration Considerations:**
   - Supabase uses `auth.uid()` -> Neon uses `auth.user_id()`
   - Password hashes are incompatible - users need to reset passwords
   - OAuth users can migrate seamlessly

**Pros:** True serverless, branching, auto-suspend saves costs
**Cons:** Auth migration is complex, RLS policy changes needed

---

### Option 4: MIGRATE TO CONVEX (High Effort - Major Refactor)

**Convex Free Tier:**
- 1GB storage
- No egress limits (metered by function execution)
- Built-in caching and real-time

**Why Consider It:**
- TypeScript-first (matches your frontend)
- Automatic real-time without polling
- No N+1 query problems
- Built-in file storage

**Why NOT:**
- Major refactor required
- Different query paradigm (no SQL)
- Lock-in to Convex schema format

**Migration would require:**
1. Rewrite all database queries as Convex functions
2. Rewrite schema from SQL to Convex schema
3. Migrate data via export/import
4. Update all frontend API calls

**Verdict:** Only consider if starting fresh or willing to do major refactor.

---

## CODE FIXES NEEDED (Apply Before Feb 2 Reset)

### Critical: Fix These Files

#### 1. Citation Storage - Full Fetch Pattern
**File:** `backend/app/engines/citation/storage.py`
**Lines 365-394, 468-509**

**Problem:** Fetches ALL citations then filters in Python
```python
# BAD - Current code
all_rows = response.data
if filter_invalid:
    all_rows = [r for r in all_rows if r.get("is_valid")]
```

**Fix:** Push filtering to database
```python
# GOOD - Filter at database level
query = self.client.table("citations").select("*").eq("source_document_id", document_id)
if filter_invalid:
    query = query.eq("is_valid", True)
if filter_act_sources:
    query = query.neq("source_type", "act")
```

#### 2. useDocumentStatus Polling
**File:** `frontend/src/hooks/useDocumentStatus.ts`
**Line 117**

**Problem:** Polls every 5 seconds
```typescript
const POLLING_INTERVAL_MS = 5000;
```

**Fix:** Increase to 30s or rely on WebSocket
```typescript
const POLLING_INTERVAL_MS = 30000; // 30 seconds instead of 5
```

#### 3. Global Search Parallel Queries
**File:** `backend/app/services/global_search_service.py`
**Lines 125-186**

**Problem:** Fetches ALL matters then runs parallel search on each
**Fix:** Implement server-side aggregation or limit concurrent searches

#### 4. Select * Patterns
Replace across codebase:
```python
# BAD
.select("*")

# GOOD - Only select needed columns
.select("id, name, created_at")
```

---

## RECOMMENDED ACTION PLAN

### Immediate (Before Feb 2):
1. **Increase polling interval** from 5s to 30s
2. **Add browser caching** via localStorage
3. **Prepare Cloudflare Worker** to proxy API calls

### Short-term (After Service Restored):
1. **Fix select(*) queries** - specify columns
2. **Push filtering to database** - stop Python-side filtering
3. **Move file storage to S3** with CloudFront CDN

### Medium-term (If Issues Continue):
1. **Migrate database to Neon** for better serverless model
2. **Implement Redis caching** for hot queries
3. **Consider read replicas** for analytics queries

### Long-term (If Major Refactor Needed):
1. Evaluate Convex for greenfield features
2. Consider self-hosting Supabase on AWS/Railway

---

## NEW: PostgreSQL Covering Indexes (From YouTube Videos)

**Key Insight:** Your indexes help FIND rows but queries still hit the main table for data.

**Solution:** Covering indexes with `INCLUDE` keyword store extra columns IN the index.

```sql
-- BEFORE: Index helps find, but still needs table lookup
CREATE INDEX idx_citations_matter ON citations(matter_id);

-- AFTER: Index-only scan, no table lookup needed
CREATE INDEX idx_citations_matter_covering ON citations(matter_id)
INCLUDE (id, act_name, verification_status, is_valid);
```

**Migration created:** `supabase/migrations/20260130000002_add_covering_indexes_egress_optimization.sql`

This migration adds covering indexes for:
- **citations** - document and matter queries
- **bounding_boxes** - page-based retrieval (89 MB table!)
- **chunks** - document chunks listing
- **entity_mentions** - entity lookups
- **events** - timeline queries
- **processing_jobs** - polling queries (5s interval!)
- **activities** - user feeds

**Estimated impact:** Could reduce egress by 50-80% for read-heavy queries.

---

## Quick Reference: Service Comparisons

| Feature | Supabase Free | Neon Free | AWS (Free Tier) | Convex Free |
|---------|---------------|-----------|-----------------|-------------|
| Database | 500MB | 500MB | RDS: 20GB | 1GB |
| Storage | 1GB | N/A | S3: 5GB | 1GB |
| Egress | 5GB cached | Unlimited* | 15GB/mo | Unlimited* |
| Auth | Built-in | Neon Auth | Cognito | Clerk/Auth0 |
| Realtime | Yes | No | AppSync | Yes |
| Price After Free | $25/mo | Pay-as-go | Pay-as-go | $25/mo |

*Unlimited = metered differently, not by egress

---

## Sources

- [Supabase Egress Docs](https://supabase.com/docs/guides/platform/manage-your-usage/egress)
- [Neon Migration Guide](https://neon.com/docs/import/migrate-from-supabase)
- [Cloudflare Workers + Supabase](https://github.com/dijonmusters/supabase-data-at-the-edge)
- [Convex vs Supabase](https://www.convex.dev/compare/supabase)
- [AWS S3 Pricing](https://aws.amazon.com/s3/pricing/)
