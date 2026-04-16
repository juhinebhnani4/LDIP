-- UX-005: Track when a matter was last opened by any user
-- This enables showing "Last opened: 2 hours ago" instead of "Never opened" on matter cards.
ALTER TABLE matters ADD COLUMN IF NOT EXISTS last_opened_at timestamptz DEFAULT NULL;
