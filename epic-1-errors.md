# Code Review Findings: Forensic Deep Dive (Epic 1)

**Review Status**: 🔴 **CRITICAL FAIL**
**Scope**: Full Epic 1 (Stories 1.1 - 1.7) with Forensic Analysis of SQL & Logic

## 🚨 Critical Security Vulnerabilities (Must Fix Immediately)

### 1. Privilege Escalation / Matter Hijacking (IDOR)
- **Severity**: **CRITICAL (Showstopper)**
- **Affected File**: `supabase/migrations/20260105000002_create_matter_attorneys_table.sql`
- **Vulnerability**: The RLS policy "Owners can insert members" contains a logical flaw:
  ```sql
  OR (user_id = auth.uid() AND role = 'owner') -- Allows self-assignment!
  ```
  **Exploit**: Any authenticated user can issue an `INSERT` command to `matter_attorneys` assigning *themselves* as an `owner` to **ANY** matter (if they guess or know the UUID). The policy only checks "Are you assigning yourself?" and "Is the role owner?", ignoring whether you have permission on the matter itself.
- **Fix**: Remove this OR clause. Initial owner assignment is handled by the `security definer` trigger `on_matter_created`, so user-facing RLS does not need to allow this.

### 2. Logic Conflict / Runtime Crash (Duplicate Inserts)
- **Severity**: High
- **Affected Files**:
  - `backend/app/services/matter_service.py` (Line 157)
  - `supabase/migrations/20260105000002_create_matter_attorneys_table.sql` (Trigger `on_matter_created`)
- **Bug**: The database trigger `auto_assign_matter_owner` automatically inserts the owner record when a matter is created. However, `matter_service.py` *also* explicitly tries to insert the same record immediately after creating the matter.
- **Outcome**: This will cause a **Unique Constraint Violation** (Crash) in production whenever a user creates a matter, as the row will already exist from the trigger. The tests missed this because they mock the DB calls and don't simulate triggers.

### 3. Verification Gap: Mocked Security Tests
- **Severity**: Critical
- **Affected Files**: `backend/tests/security/test_4_layer_isolation.py`
- **Impact**: The tests utilize mocks for the database (`mock_db.table...`). This is why Vulnerability #2 (Crash) and Vulnerability #1 (RLS Flaw) were not caught. The tests are "Green" but the code is broken and insecure.

### 4. Audit Logging Gap (Layer 4)
- **Severity**: High
- **Affected File**: `backend/app/api/deps.py`
- **Impact**: API-level security events are logged to `stdout` but never written to the `audit_logs` database table, violating compliance requirements.

---

## 🟡 Medium Issues

### 5. Weak Configuration Validation
- **Severity**: Medium
- **Affected File**: `backend/app/core/config.py`
- **Impact**: `is_configured` only checks Supabase URL/Key. It ignores `supabase_jwt_secret`, meaning the app could start up in a broken state for legacy auth verification.

### 6. Code Cleanup
- **Severity**: Low
- **Affected File**: `backend/app/services/supabase/client.py`
- **Impact**: The `_create_supabase_client` function has logic to use the service key if available, but the comment says "Application handles authorization". Mixing service-role logic into the default client getter is risky; strict separation (as seen in `get_service_client`) is better.
