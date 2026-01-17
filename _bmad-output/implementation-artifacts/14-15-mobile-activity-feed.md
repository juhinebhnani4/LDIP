# Story 14.15: Mobile Activity Feed

Status: done

## Story

As a **legal attorney using LDIP on mobile or tablet**,
I want **to see the Activity Feed on smaller screens**,
so that **I can stay updated on matter activity regardless of which device I'm using**.

## Acceptance Criteria

1. **AC1: Activity Feed visible on mobile**
   - Activity Feed component renders on screens < 1024px (currently hidden)
   - Layout adapts appropriately for mobile viewport
   - No horizontal scrolling required

2. **AC2: Mobile-optimized layout**
   - On mobile: Activity Feed below Matter Cards (stacked layout)
   - On tablet: Activity Feed in collapsible sidebar or bottom sheet
   - On desktop: Current side-by-side layout preserved

3. **AC3: Responsive activity items**
   - Activity items use compact layout on mobile
   - Icons and text scale appropriately
   - Timestamps use relative format ("2h ago" vs full date)

4. **AC4: Pull-to-refresh on mobile**
   - Swipe down to refresh activity feed
   - Loading indicator during refresh
   - Haptic feedback if supported

5. **AC5: Quick Stats on mobile**
   - Quick Stats panel visible on mobile
   - Horizontal scrollable cards or stacked layout
   - Touch-friendly tap targets (min 44px)

## Tasks / Subtasks

- [x] **Task 1: Update ActivityFeed responsive behavior** (AC: #1, #2)
  - [x] 1.1 Remove `hidden lg:block` class from ActivityFeed container
  - [x] 1.2 Add responsive layout classes for mobile/tablet/desktop
  - [x] 1.3 Implement stacked layout for mobile (below matter cards)
  - [x] 1.4 Test on various viewport sizes

- [x] **Task 2: Create MobileActivityFeed variant** (AC: #3)
  - [x] 2.1 Create `frontend/src/components/features/dashboard/MobileActivityFeed.tsx`
  - [x] 2.2 Compact activity item design
  - [x] 2.3 Relative timestamps ("2h ago")
  - [x] 2.4 Smaller icons and tighter spacing

- [x] **Task 3: Implement collapsible behavior for tablet** (AC: #2)
  - [x] 3.1 Add expand/collapse toggle for tablet viewport
  - [x] 3.2 Animate expand/collapse transition
  - [x] 3.3 Remember collapsed state in localStorage

- [x] **Task 4: Add pull-to-refresh** (AC: #4)
  - [x] 4.1 Install/use pull-to-refresh library or implement custom
  - [x] 4.2 Connect to activity feed refetch
  - [x] 4.3 Add loading spinner during refresh
  - [x] 4.4 Test on touch devices

- [x] **Task 5: Update QuickStats for mobile** (AC: #5)
  - [x] 5.1 Make QuickStats horizontally scrollable on mobile
  - [x] 5.2 Or stack vertically with full-width cards
  - [x] 5.3 Ensure touch targets are min 44px
  - [x] 5.4 Test with real data

- [x] **Task 6: Update Dashboard layout** (AC: #1, #2)
  - [x] 6.1 Modify dashboard grid layout for responsive behavior
  - [x] 6.2 Mobile: Single column (cards, then activity)
  - [x] 6.3 Tablet: Two columns or collapsible sidebar
  - [x] 6.4 Desktop: Current 70/30 split

- [x] **Task 7: Write tests** (AC: all)
  - [x] 7.1 Test ActivityFeed renders on mobile viewport
  - [x] 7.2 Test responsive layout breakpoints
  - [x] 7.3 Test pull-to-refresh triggers refetch
  - [x] 7.4 Test QuickStats mobile layout

## Dev Notes

### Current State

From the audit:
- ActivityFeed has `hidden lg:block` - only visible on large screens (1024px+)
- QuickStats may have similar responsive issues
- Mobile users see only Matter Cards grid

### Breakpoints (Tailwind)

```
sm: 640px
md: 768px
lg: 1024px
xl: 1280px
2xl: 1536px
```

### Proposed Layout

```
Mobile (< 768px):
┌─────────────────┐
│   Quick Stats   │ (horizontal scroll or stacked)
├─────────────────┤
│  Matter Cards   │ (single column)
│      ...        │
├─────────────────┤
│  Activity Feed  │ (full width, compact items)
│      ...        │
└─────────────────┘

Tablet (768px - 1024px):
┌─────────────────────────┐
│      Quick Stats        │
├───────────────┬─────────┤
│ Matter Cards  │Activity │ (collapsible)
│     ...       │  Feed   │
└───────────────┴─────────┘

Desktop (> 1024px):
┌─────────────────────────────────┐
│          Quick Stats            │
├─────────────────────┬───────────┤
│    Matter Cards     │ Activity  │
│    (70% width)      │   Feed    │
│                     │  (30%)    │
└─────────────────────┴───────────┘
```

### Pull-to-Refresh Options

1. **react-pull-to-refresh** - Simple library
2. **Custom implementation** - Use touch events
3. **Native browser** - Some browsers support natively

Recommend custom implementation for control:

```typescript
const [isRefreshing, setIsRefreshing] = useState(false);
const startY = useRef(0);

const handleTouchStart = (e: TouchEvent) => {
  startY.current = e.touches[0].clientY;
};

const handleTouchMove = (e: TouchEvent) => {
  const currentY = e.touches[0].clientY;
  const diff = currentY - startY.current;
  if (diff > 80 && window.scrollY === 0) {
    setIsRefreshing(true);
    mutate(); // SWR refetch
  }
};
```

### File Structure

```
frontend/src/components/features/dashboard/
├── ActivityFeed.tsx (MODIFY - responsive)
├── MobileActivityFeed.tsx (CREATE - compact variant)
├── QuickStats.tsx (MODIFY - responsive)
└── __tests__/
    └── ActivityFeed.responsive.test.tsx
```

### References

- [Source: frontend/src/components/features/dashboard/ActivityFeed.tsx]
- [Source: frontend/src/components/features/dashboard/QuickStats.tsx]
- [Source: frontend/src/app/(dashboard)/page.tsx] - Dashboard layout
