# Palette Journal - UX & Accessibility Learnings

## 2026-09-18 - Credential Toggle & Inline Validation Alert Roles
**Learning:** In lightweight JS applications where field validation error elements are dynamically made visible (`hidden` toggled off), adding `role="alert"` directly to the error `<p>` tags enables screen readers to immediately announce error feedback when invalid inputs are submitted. Linking toggle buttons with `aria-controls` and dynamic `aria-label` ensures state changes are clear to screen reader users.
**Action:** Always include `role="alert"` on inline field error containers and explicit `aria-controls` on password/credential toggles.

## 2026-10-06 - Document Sub-Navigation Section State & ARIA Current
**Learning:** For in-page anchor navigation (like process document section links), dynamically updating `aria-current="true"` on the active section link (and removing it from non-active links) provides screen reader users with explicit section location feedback and allows CSS to maintain visual highlight indicator (`border-bottom-color` / `color`) even after focus leaves the clicked link.
**Action:** Use `aria-current="true"` on active in-page section navigation links and style via `.nav a[aria-current="true"]`.
