# Supabase Schema vs Code Implementation Audit

## Objective
Comprehensive audit comparing the Supabase database schema against codebase implementation, including migration validation.

---

## Task 1: Extract Live Schema & Migration Status

### 1.1 Load Database Credentials
- [ ] Read `.env` file for `DATABASE_URL` or Supabase credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, etc.)
- [ ] Verify Supabase CLI is installed and configured

### 1.2 Fetch Live Schema
- [ ] Connect to database using credentials from env
- [ ] Query `information_schema.tables` for all public tables
- [ ] Query `information_schema.columns` for column details (name, type, nullable, defaults)
- [ ] Query `information_schema.table_constraints` for primary keys, foreign keys, unique constraints

### 1.3 Check Migration Status
- [ ] List all local migration files in `supabase/migrations/`
- [ ] Query `supabase_migrations.schema_migrations` table for applied migrations
- [ ] Compare local vs applied migrations
- [ ] Identify pending/unapplied migrations
- [ ] Detect schema drift (DB changes not reflected in migrations)

---

## Task 2: Table-to-Code Mapping

### 2.1 Backend Analysis
- [ ] Scan `backend/app/models/` for SQLAlchemy/Pydantic models
- [ ] Map each model to its corresponding DB table
- [ ] Extract field names and types from models
- [ ] Scan `backend/app/api/routes/` for table references in queries

### 2.2 Frontend Analysis
- [ ] Scan `frontend/src/types/` for TypeScript interfaces
- [ ] Scan `frontend/src/lib/api/` for Supabase client calls
- [ ] Map frontend types to corresponding tables
- [ ] Check `frontend/src/stores/` for table references

### 2.3 Generate Mapping Matrix
- [ ] Create table: `DB Table | Backend Model | Backend File:Line | Frontend Type | Frontend File:Line | API Routes`

---

## Task 3: Identify Discrepancies

### 3.1 Migration Issues
- [ ] List migrations in folder but not applied to DB
- [ ] List schema changes in DB not in any migration (drift)
- [ ] Flag migrations applied out of order

### 3.2 Orphaned Entities
- [ ] Tables in DB with no code references (orphaned tables)
- [ ] Models/types in code referencing non-existent tables (orphaned code)
- [ ] Columns in DB not mapped to any model field
- [ ] Model fields not matching any DB column

### 3.3 Name Mismatches
- [ ] Column names using `snake_case` vs code using `camelCase`
- [ ] Table name vs model class name inconsistencies
- [ ] Enum value mismatches between DB and code

### 3.4 Type Mismatches
- [ ] `uuid` (DB) vs `string` (code)
- [ ] `timestamptz` (DB) vs `string`/`Date` (code)
- [ ] `jsonb` (DB) vs specific object types (code)
- [ ] `integer` (DB) vs `number` (code) precision issues
- [ ] Array types alignment

### 3.5 Nullable Mismatches
- [ ] DB `NOT NULL` columns mapped to optional types in code
- [ ] DB nullable columns mapped to required types in code
- [ ] Default value handling inconsistencies

---

## Task 4: Generate Audit Report

### 4.1 Report Sections
- [ ] **Executive Summary**: Overall health score, critical issues count
- [ ] **Migration Status Table**: `Migration File | Status | Applied Timestamp`
- [ ] **Table Mapping Matrix**: Full mapping with file:line links
- [ ] **Issues List**: Categorized by severity (error/warning/info)
- [ ] **Recommendations**: Prioritized action items

### 4.2 Output Format
- [ ] Generate markdown report at `_bmad-output/reports/supabase-audit-report.md`
- [ ] Include clickable file:line references
- [ ] Add severity badges for each issue

---

## Execution Commands Reference

```bash
# Load env and check Supabase CLI
source .env  # or use dotenv

# Fetch live schema
psql $DATABASE_URL -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"

# Get column details
psql $DATABASE_URL -c "SELECT table_name, column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position;"

# Check applied migrations
psql $DATABASE_URL -c "SELECT * FROM supabase_migrations.schema_migrations ORDER BY version;"

# List local migrations
ls -la supabase/migrations/
```

---

## Success Criteria
- All migrations accounted for (applied or flagged as pending)
- Every DB table mapped to at least one code reference
- No type mismatches between DB and code
- No orphaned tables or code references
- Clear remediation steps for any issues found
