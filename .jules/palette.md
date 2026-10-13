# Palette Journal - UX & Accessibility Learnings

## 2026-09-18 - Document Navigation Active Indicator & Screen Reader Context
**Learning:** For in-page sticky document navigation (hash links pointing to section headings), dynamically setting `aria-current="true"` on the active link upon click or section reset provides immediate context for screen reader users and allows CSS targeting for clear active visual indicators (`.document-nav a[aria-current="true"]`).
**Action:** Always pair in-page navigation link focus shifts with `aria-current="true"` state updates.

## 2026-09-18 - Credential Toggle & Inline Validation Alert Roles
**Learning:** In lightweight JS applications where field validation error elements are dynamically made visible (`hidden` toggled off), adding `role="alert"` directly to the error `<p>` tags enables screen readers to immediately announce error feedback when invalid inputs are submitted. Linking toggle buttons with `aria-controls` and dynamic `aria-label` ensures state changes are clear to screen reader users.
**Action:** Always include `role="alert"` on inline field error containers and explicit `aria-controls` on password/credential toggles.
