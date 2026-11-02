# Book studio — baseline

# Label Every Form Control

Every input needs a programmatic name. A placeholder is not a label—it vanishes on typing and screen readers may skip it. Use a visible `<label for>` tied to the input's `id`; reserve `aria-label` for cases where no visible text fits (e.g., icon-only search).

```html
<label for="email">Email</label>
<input id="email" type="email" autocomplete="email">
```

Add `autocomplete` hints (`email`, `name`, `tel`, `current-password`) so browsers and assistive tech can fill fields correctly. For grouped controls like radio sets, wrap them in `<fieldset>` with a `<legend>`.

**Concrete check:** Run axe DevTools on the form and confirm zero "form elements must have labels" violations. Then Tab through—each field should announce its purpose, not just "edit text."

## Make Keyboard Interaction Work

Every interactive element—links, buttons, inputs, custom widgets—must be reachable and operable by keyboard alone. Tab moves focus forward, Shift+Tab backward, Enter activates links and buttons, Space toggles checkboxes and activates buttons, and Escape closes dialogs or menus. If you build a custom dropdown or modal, you own this behavior; native `<button>` and `<a>` give it to you for free.

Never remove the focus outline without a replacement. This is the most common keyboard bug:

```css
/* Bad: outline: none; with nothing in its place */
:focus-visible { outline: 2px solid #005fcc; outline-offset: 2px; }
```

**Concrete check:** unplug your mouse and complete your app's main task using only the keyboard. Watch for focus that disappears, gets trapped in a widget, or lands on invisible elements. Fix each one before shipping.

## Write Clear Error Messages

An error only helps if users can perceive it. Don't rely on red borders alone—announce the message programmatically and tie it to the field.

```html
<label for="email">Email</label>
<input id="email" type="email" autocomplete="email"
       aria-describedby="email-err" aria-invalid="true">
<span id="email-err" role="alert">Enter an email like name@example.com</span>
```

`role="alert"` makes screen readers announce the message when it appears; `aria-describedby` links it to the input so it's read on focus; `aria-invalid` flags the field. Write plain language that says what to do, not just "invalid."

**Concrete check:** submit an invalid form with a screen reader running. Confirm the error is announced and focus moves to the first problem field.

## Editorial

# Editorial Handoff: Accessibility Field Guide

## Introduction

This guide is a three-chapter field guide for junior developers improving accessibility in small web apps. It covers form labeling, keyboard interaction, and error messages, with a concrete check in each chapter. The chapters are intentionally short (under 150 words each) and non-overlapping: Chapter 1 covers programmatic names, Chapter 2 covers focus and operability, Chapter 3 covers error perception and association.

## Reading Order

Read in the given sequence: **Label Every Form Control → Make Keyboard Interaction Work → Write Clear Error Messages.** The order follows the user's path through a form (identify fields, operate them, recover from mistakes) and builds naturally: Chapter 3's `aria-describedby`/`aria-invalid` assumes the labeling concepts from Chapter 1.

## Consistency Corrections

1. **Heading levels are inconsistent.** Chapter 1 uses `#` (H1), Chapters 2 and 3 use `##` (H2). Standardize all three to `##` so the guide's own title can be the sole H1.
2. **Code comment mismatch in Chapter 2.** The comment says "Bad: outline: none; with nothing in its place," but the code shown is the *good* replacement. Reword to something like `/* Good: visible focus indicator */` or show the bad line separately.
3. **Terminology drift.** Chapter 1 says "assistive tech," Chapter 3 says "screen reader." Pick one convention (e.g., "assistive technology (AT)" on first use, then "AT") and apply throughout.
4. **Check phrasing varies.** Chapter 1: "Concrete check:"; Chapter 2: "Concrete check:"; Chapter 3: "Concrete check:". These are consistent—keep the bold label format uniform.
5. **Example email mismatch.** Chapter 1 uses `name@example.com` implicitly via `type="email"`; Chapter 3's error text uses `name@example.com`. Align examples so the same sample value appears in both.
6. **`autocomplete` token list.** Chapter 1 lists `current-password` but the example uses `email`. Fine, but note in copy that tokens are field-specific to avoid readers copying the wrong token.

## Facts Needing Sources

- **"A placeholder is not a label… screen readers may skip it."** Needs a citation (e.g., WAI-ARIA Authoring Practices or WCAG technique) supporting the claim about screen reader behavior.
- **"`role="alert"` makes screen readers announce the message when it appears."** Generally true but support varies; cite ARIA spec or a testing reference, and note it should not be overused.
- **"`aria-describedby` links it to the input so it's read on focus."** Verify and cite; behavior depends on AT and whether the description is present at focus time.
- **"This is the most common keyboard bug"** (focus outline removal). Needs a source or should be softened to "a very common bug."
- **Keyboard key mappings** (Enter/Space/Escape behaviors). Cite WAI-ARIA Authoring Practices for custom widget expectations.
- **axe DevTools violation name** "form elements must have labels." Confirm exact rule ID/name against current axe documentation.

## Open Items

- Confirm each chapter is under 150 words after edits (Chapter 1 is closest to the limit).
- Decide whether to add a one-line "why it matters" sentence per chapter or keep the terse field-guide tone.

## Title

Accessibility Field Guide for Small Web Apps
