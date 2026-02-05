# Tech-Spec: Epic 6 - User Adoption

**Created:** 2026-01-27
**Status:** Ready for Development
**Epic:** 6 - User Adoption (Phase 5)
**FRs Covered:** FR5.1, FR5.2, FR5.3
**Gaps Addressed:** #8, #9, #10

---

## Overview

### Problem Statement

New users landing on LDIP face **information overload paralysis**. The dashboard exposes all features immediately - Timeline, Entities, Contradictions, Citations, Q&A, Verification, Documents - with no guidance on where to start or what each feature does. Power users love the depth; new users freeze.

Additionally, users have no control over processing intensity. Every matter runs "deep analysis" regardless of urgency, wasting time and API costs for quick triage scenarios.

### Solution

Implement a **progressive disclosure system** that:
1. Hides advanced features (bulk ops, keyboard shortcuts, cross-engine links) for new users
2. Provides a **10-step onboarding wizard** triggered after first data upload
3. Offers **"Try Sample Case"** for hands-on exploration without uploading real documents
4. Adds **Quick Scan vs Deep Analysis** mode toggle per matter

### Scope

**In Scope:**
- Story 6.1: Progressive Disclosure UI with Power User Mode toggle
- Story 6.2: 10-step Onboarding Wizard (3 phases)
- Story 6.3: "Import Sample Documents" button (descoped from auto-created matter)
- Story 6.4: Analysis Mode toggle (Quick Scan / Deep Analysis)

**Out of Scope:**
- Progressive unlocking based on usage patterns (v2 backlog)
- Video tutorials or external help content
- A/B testing framework for onboarding variants
- Analytics/tracking for adoption metrics

---

## Context for Development

### Codebase Patterns

**User Preferences (SWR + API pattern):**
```typescript
// frontend/src/hooks/useUserPreferences.ts
const { preferences, updatePreferences, isLoading } = useUserPreferences();
// Returns: emailNotificationsProcessing, emailNotificationsVerification, browserNotifications, theme
// Pattern: SWR fetch + optimistic updates + toast feedback
```

**Settings Section Component Pattern:**
```typescript
// frontend/src/components/features/settings/AppearanceSection.tsx
<Card>
  <CardHeader>
    <CardTitle>Theme</CardTitle>
    <CardDescription>Select your preferred theme</CardDescription>
  </CardHeader>
  <CardContent>
    {/* Selection UI */}
  </CardContent>
</Card>
```

**Feature Tour Pattern (existing):**
```typescript
// frontend/src/components/features/help/FeatureTour.tsx
const TOUR_STORAGE_KEY = 'ldip-feature-tour-completed';
// Uses spotlight overlay + tooltip pointing to data-tour attributes
// 5 steps currently, expand to 10
```

**Matter Settings Dialog Pattern:**
```typescript
// frontend/src/components/features/matter/MatterSettingsDialog.tsx
// Uses Dialog + Select components
// Permission gated: owner/editor only
// Pattern: Local state → API call → toast feedback
```

### Files to Reference

| Category | File | Purpose |
|----------|------|---------|
| User Prefs Hook | `frontend/src/hooks/useUserPreferences.ts` | Extend for powerUserMode |
| User Prefs Types | `frontend/src/lib/api/types.ts` | Add new preference fields |
| Settings Sections | `frontend/src/components/features/settings/` | Add PowerUserSection |
| Feature Tour | `frontend/src/components/features/help/FeatureTour.tsx` | Expand to wizard |
| Bulk Operations | `frontend/src/components/features/dashboard/BulkMatterSelectionToolbar.tsx` | Gate with powerUserMode |
| Matter Settings | `frontend/src/components/features/matter/MatterSettingsDialog.tsx` | Add analysisMode |
| Matter Types | `frontend/src/types/matter.ts` | Add AnalysisMode type |
| Matter Model | `backend/app/models/matter.py` | Add analysis_mode field |
| Users API | `backend/app/api/routes/users.py` | Extend preferences endpoint |
| Dashboard | `frontend/src/components/features/dashboard/DashboardHeader.tsx` | Sample case button |

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Power User Mode storage | Database (user_preferences) | Persists across devices, not just localStorage |
| Onboarding state | Database + localStorage hybrid | localStorage for in-progress, DB for completion |
| Wizard library | Expand existing FeatureTour | Already has spotlight/tooltip pattern, avoid new dependency |
| Sample case approach | On-demand import, not auto-created | Respects user agency, reduces storage costs |
| Analysis mode default | `deep_analysis` | Existing behavior preserved, opt-in to quick |
| Backward compatibility | Existing users get powerUserMode=true | No disruption to current workflows |

---

## Implementation Plan

### Database Migrations

**Migration: `supabase/migrations/YYYYMMDD_add_user_adoption_features.sql`**

```sql
-- Story 6.1 & 6.2: User adoption preferences
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS power_user_mode BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS onboarding_stage VARCHAR(20) DEFAULT NULL;

-- Backward compatibility: existing users get power_user_mode = true
UPDATE user_preferences SET power_user_mode = true WHERE created_at < '2026-01-27';

-- For users without preferences row yet (edge case)
INSERT INTO user_preferences (user_id, power_user_mode)
SELECT id, true FROM auth.users
WHERE id NOT IN (SELECT user_id FROM user_preferences)
AND created_at < '2026-01-27';

-- Story 6.4: Analysis mode for matters
ALTER TABLE matters
ADD COLUMN IF NOT EXISTS analysis_mode VARCHAR(20) DEFAULT 'deep_analysis'
CHECK (analysis_mode IN ('quick_scan', 'deep_analysis'));

-- Comment for documentation
COMMENT ON COLUMN user_preferences.power_user_mode IS 'When false, hides advanced features (bulk ops, keyboard shortcuts)';
COMMENT ON COLUMN user_preferences.onboarding_stage IS 'Current wizard step: welcome|upload|settings|summary|timeline|entities|contradictions|citations|qa|verification';
COMMENT ON COLUMN matters.analysis_mode IS 'quick_scan skips contradiction engine, reduces chunk overlap; deep_analysis runs all engines';
```

---

### Tasks

#### Story 6.1: Progressive Disclosure UI

- [ ] **Task 6.1.1:** Database migration - add `power_user_mode` to user_preferences
- [ ] **Task 6.1.2:** Backend - extend `/api/users/me/preferences` to include `powerUserMode`
- [ ] **Task 6.1.3:** Frontend types - add `powerUserMode` to `UserPreferences` interface
- [ ] **Task 6.1.4:** Frontend hook - update `useUserPreferences` to handle new field
- [ ] **Task 6.1.5:** Create `PowerUserSection.tsx` settings component with toggle
- [ ] **Task 6.1.6:** Add PowerUserSection to settings page
- [ ] **Task 6.1.7:** Create `usePowerUserMode()` convenience hook
- [ ] **Task 6.1.8:** Gate `BulkMatterSelectionToolbar` with powerUserMode check
- [ ] **Task 6.1.9:** Gate keyboard shortcuts in `HelpButton.tsx` (advanced shortcuts only)
- [ ] **Task 6.1.10:** Gate cross-engine correlation links (timeline → contradiction links)
- [ ] **Task 6.1.11:** Gate advanced export options (court-ready certification details)
- [ ] **Task 6.1.12:** Add "Power User" badge/indicator when mode is enabled
- [ ] **Task 6.1.13:** Write tests for progressive disclosure gating

#### Story 6.2: Onboarding Wizard

- [ ] **Task 6.2.1:** Database migration - add `onboarding_completed`, `onboarding_stage` to user_preferences
- [ ] **Task 6.2.2:** Backend - extend preferences endpoint for onboarding fields
- [ ] **Task 6.2.3:** Frontend types - add onboarding fields to UserPreferences
- [ ] **Task 6.2.4:** Create `OnboardingWizard.tsx` component (expand FeatureTour pattern)
- [ ] **Task 6.2.5:** Implement wizard step 1: Dashboard overview (matter cards, search)
- [ ] **Task 6.2.6:** Implement wizard step 2: Upload flow explanation
- [ ] **Task 6.2.7:** Implement wizard step 3: Matter settings (verification, analysis mode)
- [ ] **Task 6.2.8:** Implement wizard step 4: Summary tab
- [ ] **Task 6.2.9:** Implement wizard step 5: Timeline tab
- [ ] **Task 6.2.10:** Implement wizard step 6: Entities tab
- [ ] **Task 6.2.11:** Implement wizard step 7: Contradictions tab
- [ ] **Task 6.2.12:** Implement wizard step 8: Citations tab
- [ ] **Task 6.2.13:** Implement wizard step 9: Q&A Chat panel
- [ ] **Task 6.2.14:** Implement wizard step 10: Verification + Export
- [ ] **Task 6.2.15:** Add skip/dismiss functionality with confirmation
- [ ] **Task 6.2.16:** Implement progress persistence (localStorage + DB sync)
- [ ] **Task 6.2.17:** Add wizard trigger logic (after first upload completes)
- [ ] **Task 6.2.18:** Add "Restart Tour" button in Help menu
- [ ] **Task 6.2.19:** Write tests for wizard flow and persistence

#### Story 6.3: Sample Case Import

- [ ] **Task 6.3.1:** Create sample documents (3 anonymized PDFs in `/public/samples/`)
- [ ] **Task 6.3.2:** Backend - create `/api/samples/import` endpoint
- [ ] **Task 6.3.3:** Backend - implement matter creation with sample docs
- [ ] **Task 6.3.4:** Backend - trigger document processing pipeline for samples
- [ ] **Task 6.3.5:** Frontend - add "Try with Sample Documents" button to empty dashboard
- [ ] **Task 6.3.6:** Frontend - add loading state during sample import
- [ ] **Task 6.3.7:** Frontend - add "Sample Case" badge to matter card
- [ ] **Task 6.3.8:** Frontend - add easy delete option for sample matter
- [ ] **Task 6.3.9:** Write tests for sample import flow

#### Story 6.4: Analysis Mode Toggle

- [ ] **Task 6.4.1:** Database migration - add `analysis_mode` to matters table
- [ ] **Task 6.4.2:** Backend - add `AnalysisMode` enum to matter model
- [ ] **Task 6.4.3:** Backend - update matter create/update endpoints
- [ ] **Task 6.4.4:** Backend - implement conditional engine invocation based on mode
- [ ] **Task 6.4.5:** Frontend types - add `AnalysisMode` type and update Matter interfaces
- [ ] **Task 6.4.6:** Frontend - add analysis mode selector to MatterSettingsDialog
- [ ] **Task 6.4.7:** Frontend - add analysis mode selector to matter creation flow
- [ ] **Task 6.4.8:** Frontend - show current mode indicator on matter card
- [ ] **Task 6.4.9:** Document Quick Scan vs Deep Analysis differences in UI tooltip
- [ ] **Task 6.4.10:** Write tests for analysis mode toggle and engine behavior

---

### Acceptance Criteria

#### Story 6.1: Progressive Disclosure UI

- [ ] **AC 6.1.1:** Given a NEW user (created after feature launch), when they log in, then `power_user_mode` is `false` and advanced features are hidden
- [ ] **AC 6.1.2:** Given an EXISTING user (created before feature launch), when they log in after deployment, then `power_user_mode` is `true` and all features remain visible
- [ ] **AC 6.1.3:** Given a user with `power_user_mode = false`, when they view the dashboard, then bulk selection toolbar is NOT visible
- [ ] **AC 6.1.4:** Given a user with `power_user_mode = false`, when they press keyboard shortcuts (Y/N/J/K), then shortcuts do NOT trigger actions
- [ ] **AC 6.1.5:** Given a user in Settings, when they toggle "Power User Mode" ON, then advanced features become visible immediately
- [ ] **AC 6.1.6:** Given a user enables Power User Mode, when they refresh or log in on another device, then the setting persists

#### Story 6.2: Onboarding Wizard

- [ ] **AC 6.2.1:** Given a new user completes their first document upload, when processing finishes, then the onboarding wizard appears automatically
- [ ] **AC 6.2.2:** Given the wizard is active, when user completes all 10 steps, then `onboarding_completed` is set to `true`
- [ ] **AC 6.2.3:** Given the wizard is active, when user clicks "Skip", then a confirmation appears and wizard can be dismissed
- [ ] **AC 6.2.4:** Given a user dismisses the wizard at step 5, when they click "Restart Tour" in Help menu, then wizard resumes from step 1
- [ ] **AC 6.2.5:** Given a user has completed onboarding, when they log in again, then wizard does NOT appear
- [ ] **AC 6.2.6:** Given wizard step 5 (Timeline), when spotlight highlights the tab, then tooltip explains "Events extracted chronologically from your documents"

#### Story 6.3: Sample Case Import

- [ ] **AC 6.3.1:** Given a new user with no matters, when they view the dashboard, then "Try with Sample Documents" button is visible
- [ ] **AC 6.3.2:** Given user clicks "Try with Sample Documents", when import completes, then a matter named "Sample Case" appears with 3 documents
- [ ] **AC 6.3.3:** Given the sample matter exists, when user views it, then timeline shows events, entities are extracted, and Q&A works
- [ ] **AC 6.3.4:** Given a sample matter, when user clicks delete, then matter is removed without extra confirmation (it's demo data)
- [ ] **AC 6.3.5:** Given user has existing matters, when they view dashboard, then "Try with Sample Documents" button is hidden

#### Story 6.4: Analysis Mode Toggle

- [ ] **AC 6.4.1:** Given a user creates a new matter, when they view matter settings, then analysis mode defaults to "Deep Analysis"
- [ ] **AC 6.4.2:** Given a matter with `analysis_mode = 'quick_scan'`, when documents are processed, then contradiction engine is skipped
- [ ] **AC 6.4.3:** Given a matter with `analysis_mode = 'deep_analysis'`, when documents are processed, then all engines run (including contradictions)
- [ ] **AC 6.4.4:** Given user changes analysis mode after documents are processed, when they save, then a warning appears: "Existing analysis will not be re-run"
- [ ] **AC 6.4.5:** Given matter card on dashboard, when analysis mode is 'quick_scan', then a "Quick" badge is visible

---

## Additional Context

### Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Supabase migration access | Infrastructure | Available |
| shadcn/ui Switch component | Frontend | Already installed |
| shadcn/ui Dialog component | Frontend | Already installed |
| Existing FeatureTour component | Frontend | Expand, don't replace |
| Document processing pipeline | Backend | Modify for analysis_mode |

### Testing Strategy

**Unit Tests:**
- `usePowerUserMode()` hook returns correct state
- `useUserPreferences()` handles new fields
- Analysis mode enum validation in backend
- Progressive disclosure component gating logic

**Integration Tests:**
- Preferences API accepts/returns new fields
- Sample import creates matter + triggers pipeline
- Analysis mode affects engine invocation

**E2E Tests (Playwright):**
- New user flow: signup → empty dashboard → sample import → wizard
- Power user toggle: enable → bulk ops visible → disable → hidden
- Analysis mode: create matter with quick_scan → verify no contradictions tab populated

### Quick Scan vs Deep Analysis Behavior

| Aspect | Quick Scan | Deep Analysis |
|--------|------------|---------------|
| OCR | Full | Full |
| Chunking | Larger chunks, less overlap | Standard chunks with overlap |
| Entity Extraction | Basic (names, orgs) | Full (+ relationships) |
| Timeline | Yes | Yes |
| Citations | Yes | Yes |
| Contradictions | **Skipped** | Full analysis |
| Q&A | Works (fewer chunks indexed) | Full semantic search |
| Processing Time | ~40% faster | Standard |
| API Cost | ~30% lower | Standard |

### Onboarding Wizard Steps Detail

| Step | Phase | Target Element | Tooltip Content |
|------|-------|----------------|-----------------|
| 1 | Getting Started | `[data-tour="matter-list"]` | "Your matters appear here. Each matter is a case or project." |
| 2 | Getting Started | `[data-tour="upload-button"]` | "Upload documents to start. We support PDF, DOCX, and images." |
| 3 | Getting Started | `[data-tour="matter-settings"]` | "Configure verification requirements and analysis depth here." |
| 4 | Exploring Results | `[data-tour="summary-tab"]` | "AI-generated overview of your case with key findings." |
| 5 | Exploring Results | `[data-tour="timeline-tab"]` | "Events extracted chronologically from your documents." |
| 6 | Exploring Results | `[data-tour="entities-tab"]` | "People, organizations, and locations identified in your case." |
| 7 | Exploring Results | `[data-tour="contradictions-tab"]` | "Conflicting statements flagged for your review." |
| 8 | Exploring Results | `[data-tour="citations-tab"]` | "Key passages with direct links to source documents." |
| 9 | Taking Action | `[data-tour="qa-panel"]` | "Ask questions in natural language. AI searches your documents." |
| 10 | Taking Action | `[data-tour="verification-tab"]` | "Review AI findings before export. Required for court-ready mode." |

### Notes

- **Backward Compatibility:** Existing users are unaffected. `power_user_mode = true` by default for pre-launch accounts.
- **Feature Flags:** Consider wrapping entire Epic 6 in a feature flag for staged rollout.
- **Analytics (future):** Track wizard completion rate, step drop-off, time-to-first-upload for adoption metrics.
- **Accessibility:** Wizard must support keyboard navigation, focus trapping, and screen reader announcements.

---

## Files Changed Summary

### New Files
```
frontend/src/components/features/settings/PowerUserSection.tsx
frontend/src/components/features/onboarding/OnboardingWizard.tsx
frontend/src/hooks/usePowerUserMode.ts
backend/app/api/routes/samples.py
public/samples/sample-doc-1.pdf
public/samples/sample-doc-2.pdf
public/samples/sample-doc-3.pdf
supabase/migrations/YYYYMMDD_add_user_adoption_features.sql
```

### Modified Files
```
frontend/src/hooks/useUserPreferences.ts
frontend/src/lib/api/types.ts
frontend/src/types/matter.ts
frontend/src/components/features/settings/index.tsx (or page)
frontend/src/components/features/help/FeatureTour.tsx
frontend/src/components/features/help/HelpButton.tsx
frontend/src/components/features/dashboard/BulkMatterSelectionToolbar.tsx
frontend/src/components/features/dashboard/DashboardHeader.tsx
frontend/src/components/features/matter/MatterSettingsDialog.tsx
frontend/src/components/features/matter/MatterCard.tsx
backend/app/models/matter.py
backend/app/api/routes/users.py
backend/app/api/routes/matters.py
backend/app/workers/tasks/document_tasks.py (conditional engine invocation)
```

---

**Estimated Effort:** Medium-High (4 stories, ~45 tasks)
**Recommended Order:** 6.1 → 6.4 → 6.2 → 6.3
