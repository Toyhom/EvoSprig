# Book studio — evolved

## Forms: Label Everything, Clearly

Every input needs a visible label tied to it with `for`/`id`. Placeholders vanish once users type and aren't reliable accessible names—never use them as the only label.

```html
<label for="email">Email</label>
<input id="email" type="email" name="email">

<fieldset>
  <legend>Contact preference</legend>
  <label><input type="radio" name="contact" value="email"> Email</label>
  <label><input type="radio" name="contact" value="phone"> Phone</label>
</fieldset>
```

Group related controls (radios, checkboxes) in a `fieldset` with a `legend` so screen readers announce the group's purpose.

**Check:** Inspect each input in DevTools' Accessibility pane, or tab through with a screen reader—every field should announce a meaningful name, not "edit text" or the placeholder.

## Keyboard Interaction: Make Everything Reachable

Tab order should follow visual order—avoid positive `tabindex` values, which scramble it. Never remove focus outlines; style them instead with `:focus-visible`. Custom widgets (menus, dialogs, toggles) must respond to Enter/Space to activate and Escape to close.

```css
button:focus-visible { outline: 3px solid #1a73e8; outline-offset: 2px; }
```
```js
menu.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeMenu();
  if (e.key === 'Enter' || e.key === ' ') activate(e.target);
});
```

**Check:** Navigate your whole app using only Tab, Shift+Tab, Enter, and arrow keys. Focus must always be visible, and every control must be operable.

## Error Messages: Announce and Guide

When validation fails, sighted users see red text; screen reader users may hear nothing. Fix this by tying each error to its field with `aria-describedby`, and flag the field with `aria-invalid="true"`. Also render a summary at the top of the form and move focus to it on submit, so users learn what went wrong before hunting through fields.

```html
<p id="email-error" role="alert">Enter a valid email address.</p>
<input type="email" id="email" name="email"
       aria-invalid="true" aria-describedby="email-error">
```

**Check:** Submit an invalid form with a screen reader running. Confirm the summary is announced, then tab to the field and verify its error message is read alongside the label.

## Editorial

# Editorial Handoff: Accessibility Field Guide for Junior Developers

## Introduction

This three-chapter field guide gives junior developers practical, low-friction ways to improve accessibility in small web apps. It deliberately scopes to three high-impact areas—forms, keyboard interaction, and error messages—and gives each chapter one concrete check so readers can verify their work immediately. The tone is direct and instructional, aimed at developers who can read HTML/CSS/JS but haven't internalized accessibility patterns. Each chapter is self-contained and under 150 words, with no intentional overlap in content.

## Reading Order

Read in the given sequence: **Forms → Keyboard Interaction → Error Messages.** The logic is cumulative. Forms establishes labeling and grouping (the structural foundation). Keyboard interaction assumes operable controls exist and addresses reachability and focus. Error messages build on both—errors are tied to labeled fields and surfaced to keyboard/screen-reader users. A reader who skips ahead will still follow each chapter, but the error-message chapter's `aria-describedby`/`aria-invalid` example lands best after the labeling chapter.

## Consistency Corrections

1. **Terminology—"screen reader" vs. "screen readers."** Chapter 1 uses the plural ("so screen readers announce"), Chapter 3 uses the singular ("with a screen reader running"). Standardize to singular "a screen reader" throughout for parallelism with the check instructions.
2. **Check formatting.** All three chapters end with a bolded **Check:** label—good. But Chapter 1's check offers two alternatives ("DevTools' Accessibility pane, or tab through with a screen reader"), while Chapters 2 and 3 give a single procedure. Consider tightening Chapter 1 to one primary check (the screen-reader tab-through) with DevTools as a fallback, to match the others' single-path style.
3. **Code comment/labeling style.** Chapter 2's JS uses `activate(e.target)` and `closeMenu()` as undefined helpers; Chapter 3's HTML is fully self-contained. Add a one-line note in Chapter 2 that these are illustrative stubs, or the junior reader may assume they're runnable.
4. **Attribute quoting.** Consistent double quotes throughout—no change needed, but confirm the final render doesn't smart-quote the code blocks.
5. **Heading style.** All three use `##` with a colon-subtitle pattern ("Forms: …", "Keyboard Interaction: …", "Error Messages: …"). Consistent—keep.
6. **"Custom widgets" scope.** Chapter 2 introduces menus/dialogs/toggles but the guide targets "small web apps." Add a half-sentence acknowledging native elements (`<button>`, `<dialog>`) cover most cases before reaching for custom ARIA—prevents juniors from over-engineering.

## Facts Needing Sources

- **"Placeholders … aren't reliable accessible names."** Accurate per WCAG/ARIA guidance, but cite the source (e.g., W3C WAI "Labeling Controls" or WCAG 2.1 SC 3.3.2) so the claim isn't asserted bare.
- **"Avoid positive `tabindex` values, which scramble [tab] order."** Correct, but link to the spec/guidance (W3C or MDN `tabindex` page) explaining why positive values break sequential focus.
- **"Never remove focus outlines; style them instead with `:focus-visible`."** The `:focus-visible` recommendation is sound; cite MDN or the CSS Selectors spec, and note browser support if the audience targets older browsers.
- **`role="alert"` behavior.** The claim that the summary/error "is announced" depends on `role="alert"` (implicit `aria-live="assertive"`). Cite the ARIA spec or MDN `role="alert"` and clarify that `role="alert"` announces on insertion—relevant because the example shows static markup, not dynamic insertion.
- **"Move focus to [the summary] on submit."** This is a recommended pattern but not universal; cite a source (e.g., GOV.UK Design System error-summary pattern or W3C WAI) and note it requires JS focus management.
- **`aria-describedby` + `aria-invalid` pairing.** Standard practice; cite W3C WAI "Describing" / ARIA `aria-invalid` docs to back the recommendation.
- **"Enter/Space to activate, Escape to close."** Cite the ARIA Authoring Practices Guide (APG) patterns for menus/dialogs, since exact key behavior varies by widget role.

**Open item for author:** confirm whether the guide should state a WCAG conformance target (e.g., 2.1 AA) in the intro; if so, that framing needs a citation and may affect how strictly the "checks" are worded.

## Title

Accessibility Field Guide for Small Web Apps
