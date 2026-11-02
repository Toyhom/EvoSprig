# Studio interface

Studio uses white surfaces, a light gray sidebar and canvas, and dark gray text. Borders, spacing and type establish the hierarchy. Small colored node icons identify models, tools and approval steps; status labels also carry text. Primary actions use a dark neutral button.

The project sidebar includes search and truncates long names while preserving the full name in a tooltip. Project actions stay next to the list; connection settings stay at the bottom. The header shows the selected project, save state and export controls. Tabs separate the workflow, resources, history, memory, evaluation and versions.

Workflow cards expose the node name, type, instruction summary and model/tool binding. Selection adds a restrained outline. The property panel and result area share the same spacing and form styles as the data pages. All counts and statuses come from the current project and run.

On narrow screens, project navigation opens in a drawer. It contains keyboard focus, closes with Escape or project selection, and returns focus to the menu button. Tabs scroll within their row; the canvas and inspector stack vertically. Focus indicators and reduced-motion preferences are supported.

## References

Reviewed on 2026-11-02; these are design references, with no third-party assets or component code copied into Studio:

- [Linear: How we redesigned the Linear UI](https://linear.app/now/how-we-redesigned-the-linear-ui) — neutral surfaces, stronger contrast, alignment and navigation density.
- [Vercel Geist](https://vercel.com/geist/introduction) — restrained borders, typography and compact controls.
- [Radix Themes](https://www.radix-ui.com/themes/docs/overview/getting-started) — consistent spacing and component states.

## Verification and next steps

Browser coverage includes the existing editing, execution, human review, evaluation, release, import and export flows, plus project filtering, long names, keyboard navigation and narrow screens. Visual review covers the desktop canvas, mobile canvas/navigation and version comparison. The first redesign retains the existing product structure; richer graph layout, larger-project navigation and a full accessibility audit remain future work. Backend deployment and concurrency optimization follow the separate [roadmap](roadmap.md).
