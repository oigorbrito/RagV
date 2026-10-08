## 2026-10-08 - Preserve visible text and dynamic ARIA state on theme toggles
**Learning:** Stateful buttons that toggle themes or settings should retain visible descriptive text alongside icons rather than collapsing to bare emojis, and dynamically reflect the target action in `aria-label` to maintain visual clarity and screen reader context.
**Action:** Always maintain explicit text labels and sync `aria-label` dynamically when toggling UI states.
