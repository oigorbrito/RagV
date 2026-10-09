# Palette Journal - UX & Accessibility Learnings

## 2026-09-18 - Credential Toggle & Inline Validation Alert Roles
**Learning:** In lightweight JS applications where field validation error elements are dynamically made visible (`hidden` toggled off), adding `role="alert"` directly to the error `<p>` tags enables screen readers to immediately announce error feedback when invalid inputs are submitted. Linking toggle buttons with `aria-controls` and dynamic `aria-label` ensures state changes are clear to screen reader users.
**Action:** Always include `role="alert"` on inline field error containers and explicit `aria-controls` on password/credential toggles.

## 2026-09-18 - Section Navigation Active States & aria-current
**Learning:** For in-page anchor navigation (like sticky section bars within a process document view), setting `aria-current="true"` dynamically on the active link provides screen readers with context on the active section while giving visual feedback via `a[aria-current]` CSS selector without adding custom classes.
**Action:** Use `aria-current="true"` on section nav links and style via `.document-nav a[aria-current]`. Re-initialize `aria-current` to the default link whenever new process content is rendered.
