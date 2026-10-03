# Design curation — IDX Leadership Diffusion

Review date: 3 October 2026. These are selections for external implementation, not dependencies already installed. The sites were reviewed through public pages/documentation; not every demo has been visually tested or individually audited for code quality/licensing.

## Primary selections

| Need | Selection | Application |
| --- | --- | --- |
| Buttons and controls | [shadcn/ui, Radix variant](https://ui.shadcn.com/docs/components/radix/button) | Primary/secondary/outline/ghost/icon buttons, inputs, badges, segmented tabs, tables, and empty/skeleton states. Adapt project tokens and adopt components selectively. |
| Complex interactions | [Radix Primitives](https://www.radix-ui.com/primitives) | Rail tooltips, dropdowns, popovers, tabs, and dialogs/sheets with focus management. Preserve working native dialogs when no additional capability is needed. |
| Icons | [Radix Icons](https://www.radix-ui.com/icons) | One SVG family for navigation/actions; use exports that actually exist. Do not mix in Lucide/Tabler icons from shadcn examples. |
| UI font | [General Sans — Fontshare](https://www.fontshare.com/fonts/general-sans) | Body text, headings, buttons, and labels at 400/500/600. My editorial choice for tables and research workspaces. Retain Geist as a fallback if the font is unavailable. |
| Numerical font | The project’s existing Geist Mono | Tickers, table numbers, and short dates; tabular numbers and right alignment. Do not use monospace for all prose. |
| Logo | Original SVG in `app/web/src/components/BrandMark.tsx` | Refine optical alignment, clear space, compact/expanded lockups, favicon, and dark-mode colors. Preserve the project’s name and identity. |
| Layout | [Astryx](https://astryx.atmeta.com/components) | References for App Shell, Side Nav, Metadata List, Table, Tab List, and Bottom Sheet. Adapt the hierarchy rather than installing the entire design system. |
| Motion | [Transitions.dev](https://transitions.dev/library.html) | References for tab indicators, tooltips, disclosures, and toasts. Short, interruptible CSS transitions; reduced-motion support is required. |
| Optional polish | [beUI](https://beui.dev/) | References for Tabs, Tooltip, Drawer, and Command Palette. Select patterns that support orientation and keyboard use. A motion library is not mandatory. |
| Evidence/context | [Beautiful UI](https://www.beautifului.dev/) | References for Context Cards, Filter/Records Table, Sidebar Nav, and Search. Keep sources, periods, coverage, and research details visible. |

Radix states that its primitives support keyboard interaction, semantics, and focus management. Test integrated behavior rather than assuming a dependency guarantees application accessibility. Radix Icons use a native 15×15 grid; test clarity at the final selected size. Fontshare identifies General Sans as Closed Source: retain the downloaded family’s license and do not assume SIL OFL or permission to modify font files. [Radix](https://www.radix-ui.com/primitives), [Icons](https://www.radix-ui.com/icons), [Fontshare catalogue](https://www.fontshare.com/), [Fontshare license explanation](https://fontshare.com/licenses/sil-ofl).

## Assessment of all 13 user-selected libraries

| Library | Decision | Rationale and limits |
| --- | --- | --- |
| [ObsidianUI](https://www.obsidianui.dev/components#component-gallery) | Landing-page reserve | The gallery emphasizes interactive/animated components; marquee, art-gallery, and text-stream patterns are unnecessary for the core research dashboard. Do not add Motion solely for decoration. |
| [Bencho](https://bencho.dev/) | Optional interaction reference | Search, hover, and label-input patterns may inspire feedback. Its heat-map demo is not automatically a suitable financial treemap implementation. |
| [Fontshare](https://fontshare.com/) | Selected | General Sans; verify the license and font assets during implementation. Satoshi is an alternative if assets cause problems; do not use both simultaneously. |
| [Transitions.dev](https://transitions.dev/library.html) | Selected motion reference | Tab-indicator, tooltip, and disclosure patterns fit. Choose free examples and do not assume access to Pro components. |
| [beUI](https://beui.dev/) | Selective reference | Includes Tabs, Tooltip, Drawer, and Command Palette. Avoid magnetic buttons, metallic/glass effects, bouncy sliders, and spinning market-number animations. |
| [Radix Primitives](https://www.radix-ui.com/primitives) | Selected interaction foundation | Adopt individual components for keyboard/focus/overlay needs without rewriting the application. |
| [Radix Icons](https://www.radix-ui.com/icons) | Selected icon family | One set for the sidebar, search, profile, chart controls, and actions. |
| [shadcn/ui](https://ui.shadcn.com/) | Selected control foundation | Choose the Radix variant explicitly; some generic component URLs redirected to Base UI during review. Do not install two primitive systems. |
| [Beautiful UI](https://www.beautifului.dev/) | Evidence/table reference | Select context/filter/search patterns. Chat, AI thinking traces, and approval cards are not requested features. |
| [Astryx](https://astryx.atmeta.com/components) | Selected layout reference | Relevant shell, navigation, metadata, tables, and responsive overlays. Check source/asset licenses before copying. |
| [Reverse UI](https://reverseui.com/#components-section) | Excluded from the core | The gallery includes logo/particle/visual effects. The project already has a logo; these effects do not improve data reading. |
| [Kinetics](https://kinetics.colorion.co/#library) | Excluded from the core | Physics/spring motion is not a primary need. Do not introduce a second motion engine or rely on movement as the only feedback. |
| [UI Arc](https://uiarc.dev/components/) | Reserve; component verification required | The research tool could not access /components; the [uiarc.dev](https://uiarc.dev/) homepage was accessible. Do not claim the inaccessible catalog was audited. |

## Implementation design rules

- A calm financial dashboard: three primary cards, clear hierarchy, and details on demand. Data density is acceptable; reduce decoration and repetitive badges.
- Use coral for branding/selected actions and green/red for signed changes with numbers and labels. Do not use red/green as buy/sell instructions.
- Use semantic light/dark tokens. Replace global inversion/filters if they damage chart/widget colors; do not simply invert the entire root.
- Body text 14–16px, tables 12–14px, metadata 11–12px. Use tabular numbers, decimal alignment, and consistent units. Avoid tiny uppercase text throughout the interface.
- Use a consistent spacing scale, readable table rows, small consistent radii, structural borders, and restrained overlay shadows.
- Default buttons 36–40px; mobile touch targets 44px. Icon-only actions need accessible names and tooltip/focus cues. Navigation uses actual links.
- Design hover/focus/selected/disabled/loading/error/empty states. Avoid transition: all, animated counters, and workspace page-load choreography.
- Motion around 120–180ms for simple feedback and 180–240ms for overlays; respect prefers-reduced-motion. Search, sorting, and filtering must not wait for animations.
- There is no requirement to install every library. Reuse React/Router/Tailwind/Recharts; add packages only for concrete needs unmet by existing code/platform capabilities.

## Dependencies and licensing

The baseline has no Radix/shadcn/Motion dependencies. The external model must record the name/version, rationale, bundle impact, and license of each addition. Use official registries/vendors, lockfiles, and named icon imports. Do not run bulk installers or replace the framework, router, charts, or package manager.

Choose free source code with an appropriate license; visual references do not automatically authorize taking all assets. Do not buy Pro access, paid fonts, subscriptions, or new services. Demonstrate React 19/Tailwind 4/Vite compatibility through an actual build.
