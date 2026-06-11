# Visual Verify — Eyes-on-Pixels UI Verification

> **When to invoke**: before marking ANY UI/frontend change "verified", and before merging/deploying a frontend change. This is the gate that CLAUDE.md "Verify UI Changes Visually — Pixels Are the Gate" and hostile-review Post-Deploy step 5 require.
>
> **Why this exists (2026-06-11)**: an FE-ARCH-02 responsive fix was marked "LIVE-VERIFIED" off the Playwright **accessibility tree** (which only proves elements exist) and shipped to production rendering badly — full-screen sheet takeover, doubled headers, content clipped off-screen, raw scrollbar troughs. The DOM is not the pixels.

## The rule

A UI change is verified ONLY after you RENDER it and LOOK at the actual screenshot image — never from a DOM / accessibility snapshot. "The DOM has the right nodes" is never an acceptable verification line. **Pixels are the gate; the DOM can't close it.**

## Protocol

1. **Enumerate every surface** the change touches (each route / tab / component). For a sweep, list them ALL and verify each — do not stop at the first that looks fine.
2. **Pick the environment.** Auth-gated pages render only where you are logged in (usually prod `www.jaanch-ai.in`, or a local dev server you have logged into). An unauthenticated page or the accessibility tree is NOT a substitute.
3. **For each surface × each width {375, 768, 1024, 1440}**: resize the viewport, navigate, take a real screenshot (`browser_take_screenshot`, not `browser_snapshot`), and actually VIEW the image.
4. **Critique each shot as a user would**: clipped text or controls off the edge? horizontal overflow / sideways scroll? raw scrollbar troughs? overlap (e.g. a floating button over content)? cramped/squeezed panels? doubled headers? does the layout look intentional or broken?
5. **Exercise the key responsive interaction** and screenshot the result too (open the drawer/sheet, trigger the table→card swap, open a dialog).
6. **Verdict per surface × width**: PASS / FAIL with the specific defect named. ANY FAIL ⇒ the change is NOT verified; fix and re-shoot.

## Output

A table of surface × width with PASS/FAIL + defect notes, then a single GO / NO-GO. If a path cannot be rendered (no auth, no data), mark it **"UNVERIFIED — visual"** explicitly — never silently assume it's fine.

## Related

- CLAUDE.md → "MANDATORY: Verify UI Changes Visually — Pixels Are the Gate"
- hostile-review → Post-Deploy Verification Protocol, step 5
- memory: `feedback-visual-is-the-gate`, `feedback-agent-gate-discipline`
