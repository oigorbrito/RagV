# Palette Journal - UX & Accessibility Learnings

## 2026-09-18 - Credential Toggle & Inline Validation Alert Roles
**Learning:** In lightweight JS applications where field validation error elements are dynamically made visible (`hidden` toggled off), adding `role="alert"` directly to the error `<p>` tags enables screen readers to immediately announce error feedback when invalid inputs are submitted. Linking toggle buttons with `aria-controls` and dynamic `aria-label` ensures state changes are clear to screen reader users.
**Action:** Always include `role="alert"` on inline field error containers and explicit `aria-controls` on password/credential toggles.

## 2026-09-18 - Document Section Navigation ARIA Current Indicator
**Learning:** For sticky in-page document navigation bars (`.document-nav`), setting `aria-current="location"` dynamically on clicked section links provides immediate context to assistive tech users regarding which section of the process document is selected, while visual styles (`.document-nav a[aria-current="location"]`) give a clear visual active state indicator.
**Action:** Always pair in-page section jump links with `aria-current="location"` state management and CSS selectors for `a[aria-current="location"]`.
