# IDX Leadership Diffusion

## Figma Make — Visual Redesign, Product Homepage & Market Intelligence Workspace

Redesign the existing **IDX Leadership Diffusion** product from the ground up visually while preserving its analytical product logic.

The current prototype is functionally organized but visually too plain. It currently resembles a clean internal analytics/admin dashboard: white canvas, repeated bordered cards, sparse hierarchy, generic sidebar, and limited visual storytelling.

Do **NOT** simply restyle the existing cards.

Create a stronger visual and information architecture.

The result should feel like:

> **an institutional equity-strategy workstation with an editorial market-intelligence layer**

rather than:

> a generic Streamlit dashboard.

---

# 1. PRODUCT

Name:

**IDX Leadership Diffusion**

Short descriptor:

**Indonesian Equity Market Intelligence**

Core question:

> Where is market leadership moving — and is that leadership broadening, concentrating, persisting, or deteriorating beneath the index surface?

The product analyzes:

```text
IDX
↓
Sector
↓
Industry
↓
Constituents
```

Individual stocks are supporting evidence.

The primary object of analysis is **market leadership**, not stock picking.

---

# 2. ANALYTICAL MODEL

Keep the main dimensions visually distinct:

### Leadership

* LEADING
* IMPROVING
* WEAKENING
* LAGGING
* UNCONFIRMED

### Diffusion

* BROADENING
* STABLE
* NARROWING
* UNCONFIRMED

### Concentration

How dependent the move is on a small number of stocks.

### Persistence

How long the leadership condition has remained intact.

### Confirmation

Independent support from:

* fundamentals,
* foreign flow,
* later optional free-float / broker / event evidence.

Never collapse these dimensions into one opaque score.

---

# 3. DESIGN REFERENCES — PRINCIPLES, NOT COPYING

Take inspiration from the product thinking of:

### Arthara

Use:

* evidence decomposition,
* concise signal interpretation,
* editorial storytelling around market data.

Do not copy:

* ticker-centric layout,
* Wyckoff styling,
* broker terminal structure.

### ClearTape

Use:

* command-center homepage,
* strong “market snapshot” hierarchy,
* separate Rotation / Leadership / Breadth / Concentration concepts.

### Koyfin

Use:

* dense but legible institutional information architecture,
* compact comparative tables,
* linked chart + table workspace,
* minimal wasted space.

### StockCharts RRG

Use:

* clear quadrant spatial language,
* trajectory tails,
* leadership movement over time.

### Finviz / TradingView

Use:

* hierarchy-aware market maps,
* visual encoding where size and color answer different questions,
* fast market scanning.

Do not visually clone any of them.

Create an original identity for IDX Leadership Diffusion.

---

# 4. MAIN DESIGN FAILURE TO FIX

The current prototype has:

* too much undifferentiated white space,
* too many cards with identical visual priority,
* no dominant market visualization in the first viewport,
* no strong summary of “what the market is saying now,”
* generic navigation,
* weak visual differentiation between observation, evidence, and conclusion,
* insufficient information density for an institutional research tool,
* transitions represented mostly as text rather than visual movement,
* little sense that the market is dynamic.

Fix all of these.

---

# 5. PRODUCT DESIGN PHILOSOPHY

The interface should communicate:

> **The market is a moving system, not a collection of metric cards.**

Prioritize:

1. movement,
2. hierarchy,
3. comparison,
4. evidence,
5. contradiction,
6. drilldown.

Cards are containers, not the design itself.

Avoid building a page from 20 detached rounded rectangles.

---

# 6. VISUAL DIRECTION

Use a sophisticated **light institutional theme**, but introduce stronger tonal contrast.

Main canvas:

`#F3F3F0`

Primary surface:

`#FAFAF8`

Elevated analytical surface:

`#FFFFFF`

Dark intelligence surface:

`#121619`

Primary text:

`#16191C`

Secondary text:

`#686E73`

Faint grid / border:

`#DFE2E1`

---

# 7. BRAND ACCENT

Introduce one distinctive non-semantic accent:

**Signal Orange**

approximately:

`#F26A3D`

Use sparingly for:

* active navigation,
* selected groups,
* interaction focus,
* chart current-position markers,
* important product calls to action.

Do NOT use orange to mean bullish.

---

# 8. SEMANTIC COLORS

Leadership / positive relative position:

Deep Blue

`#315D87`

Improving / broadening:

Teal

`#178477`

Warning / transitional:

Amber

`#B37B2D`

Weakening / narrowing:

Brick

`#B34E4C`

Neutral:

Slate

`#778089`

Use muted professional tones.

Never turn the product into a bright red/green trading screen.

---

# 9. TYPOGRAPHY

Use two typographic roles.

## Primary UI

Inter / Geist / similar neo-grotesk.

## Data / market metadata

IBM Plex Mono or similar.

Use monospace only for:

* dates,
* percentages,
* ticker symbols,
* state transitions,
* timestamps,
* methodology metadata.

Do not make entire sections monospace.

This should provide much more visual hierarchy than the current prototype.

---

# 10. DESKTOP TARGET

Primary:

**1440–1600 px desktop**

Secondary:

**1280 px laptop**

This is a workstation-first product.

Do not design mobile first.

---

# 11. NAVIGATION

Redesign the current large generic sidebar.

Use a compact left navigation approximately:

**176–192 px**

Brand section:

```
▲ IDX Leadership
  DIFFUSION
```

Navigation:

* Overview
* Leadership Map
* Groups
* Methodology

Highlight active section with:

* thin Signal Orange edge,
* subtle tonal background,
* stronger label weight.

At bottom:

```
SECTORS DATA
INDONESIA
EOD

● READY
26 AUG 2026
```

Keep it compact.

---

# 12. GLOBAL MARKET BAR

Across the top create an institutional market-control strip.

Example:

```
26 AUG 2026   |   INDUSTRY ▾   |   ELIGIBLE IDX   |   VS 1W AGO
```

Right:

```
● READY
Last refresh 17:44 WIB
Refresh
```

Avoid large form controls.

Use terminal-like compact controls.

---

# 13. CREATE TWO DIFFERENT HOMEPAGES

Design both:

## A. Public Product Homepage

Marketing / hackathon / portfolio landing page.

## B. In-App Intelligence Homepage

The actual research command center.

They should share the same visual identity but serve very different purposes.

---

# =====================================================

# PUBLIC HOMEPAGE

# =====================================================

# 14. PUBLIC HOMEPAGE — HERO

Do NOT make a generic SaaS hero with a centered headline and floating gradient blobs.

Use an editorial financial-research composition.

Desktop two-column hero.

Left approximately 40%.

Right approximately 60%.

Left:

Small eyebrow:

`INDONESIAN EQUITY MARKET INTELLIGENCE`

Headline:

# See where leadership is moving.

# See whether the market agrees.

Supporting text:

> IDX Leadership Diffusion scans the Indonesian equity market to identify emerging leadership, participation breadth, concentration, and deterioration beneath headline performance.

Primary CTA:

**Explore the Market**

Secondary:

**View Methodology**

Small metadata:

`Powered by Sectors data · End-of-day research`

---

# 15. PUBLIC HERO — PRODUCT VISUAL

Right side must show a **realistic product composition**, not generic laptop mockup.

Combine:

### Main Leadership Map

Quadrant chart.

### Floating transition panel

Example:

```
OIL & GAS

IMPROVING → LEADING
STABLE → BROADENING

Breadth
54% → 72%

20D Excess
+7.4%
```

### Small “market tape”

```
TELCO      LEADING     BROADENING
BANKS      LEADING     STABLE
COAL       LEADING     NARROWING
HEALTH     IMPROVING   BROADENING
```

This product visual should immediately communicate what the application does.

---

# 16. PUBLIC HOMEPAGE — MARKET FINGERPRINT SECTION

Create an editorial section.

Headline:

# Performance tells you what moved.

# Diffusion tells you how it moved.

Use two contrasting examples.

Left:

## Broad Leadership

```
20D Excess      +6.8%
Breadth          76%
Top-3 Share      34%
Diffusion        BROADENING
```

Visualize many constituent bars participating.

Right:

## Narrow Leadership

```
20D Excess      +8.1%
Breadth          38%
Top-3 Share      71%
Diffusion        NARROWING
```

Visualize only several dominant constituents.

Bottom statement:

> Similar headline returns. Very different market structure.

This should become a major brand story.

---

# 17. PUBLIC HOMEPAGE — THREE INTELLIGENCE LENSES

Not generic feature cards.

Create three horizontal editorial modules.

### 01 — Leadership

**Where relative strength is migrating.**

Visual:
mini quadrant / trajectory chart.

### 02 — Diffusion

**Whether participation is spreading or narrowing.**

Visual:
breadth sparkline + constituent matrix.

### 03 — Confirmation

**What supports or contradicts the move.**

Visual:
structured evidence list:

```
Fundamentals     SUPPORTIVE
Foreign Flow     CONFIRMING
Concentration    ELEVATED
```

---

# 18. PUBLIC HOMEPAGE — PRODUCT WALKTHROUGH

Large alternating screenshots.

### What Changed

> Start with meaningful changes, not hundreds of tickers.

### Leadership Map

> Follow movement in relative leadership over time.

### Group Explorer

> Decompose the move into breadth, concentration, constituents and confirmation.

### Methodology

> Every signal is inspectable, versioned and reproducible.

Avoid four tiny feature cards.

Use large product visuals.

---

# 19. PUBLIC HOMEPAGE — SECTORS DATA SECTION

Create a dark section.

Headline:

# Built on the structure beneath IDX.

Visual data flow:

```
SECTORS DATA
    ↓
IDX UNIVERSE
    ↓
SECTOR / INDUSTRY TAXONOMY
    ↓
RELATIVE PERFORMANCE
    ↓
BREADTH + DIFFUSION
    ↓
LEADERSHIP INTELLIGENCE
```

Supporting modules:

```
Market-wide coverage
Industry hierarchy
Constituent evidence
Fundamental context
Flow confirmation
```

Do not advertise fake live numbers.

---

# 20. PUBLIC HOMEPAGE — METHODOLOGY TRUST SECTION

Use a restrained research-paper aesthetic.

Headline:

# No black-box conviction score.

Show:

```
LEADERSHIP
Relative strength vs IHSG

DIFFUSION
Change in constituent participation

CONCENTRATION
Dependence on leading names

PERSISTENCE
Duration of state

CONFIRMATION
Independent evidence
```

Footer:

> Each component is measured independently and can contradict another.

This should reinforce product credibility.

---

# 21. PUBLIC HOMEPAGE — FINAL CTA

Dark closing section.

Headline:

# Look beneath the index.

Text:

> Follow leadership, breadth and participation across Indonesian equities from one market-wide research workspace.

CTA:

**Open IDX Leadership Diffusion**

Secondary:

**Read the Methodology**

---

# =====================================================

# IN-APP HOMEPAGE

# =====================================================

# 22. RENAME “WHAT CHANGED?” HOME

The first app navigation item may still say:

**Overview**

Within the page, use:

# Market Intelligence

not merely:

# What Changed?

“What Changed” becomes the primary module inside it.

This makes the homepage feel like a command center.

---

# 23. FIRST VIEWPORT — MARKET READ

The first viewport must have a visual anchor.

Structure:

```
┌────────────────────────────────────────────────────┐
│ MARKET READ                                         │
│                                                     │
│ Leadership is broadening in Energy and Healthcare, │
│ while Coal remains strong but increasingly narrow. │
│                                                     │
│ 3 improving · 4 leading · 2 weakening              │
└────────────────────────────────────────────────────┘
```

Use a dark or tinted analytical surface.

This is NOT AI commentary.

It is deterministic structured narrative.

---

# 24. MARKET READ TAPE

Under or inside the Market Read create a compact horizontal status strip:

```
IDX LEADERSHIP     SELECTIVE
BREADTH            61% ↑
BROADENING GROUPS  5
NARROWING GROUPS   3
DATA COVERAGE      734 / 812
```

Use small data cells.

Not huge KPI cards.

---

# 25. FIRST VIEWPORT MAIN GRID

Immediately below Market Read:

### LEFT — 65%

Large:

# Leadership × Diffusion Map

X:

Relative leadership.

Y:

Breadth / diffusion momentum.

Groups represented as points.

Current position emphasized.

4W trajectory tails visible.

### RIGHT — 35%

# Material Shifts

A ranked vertical feed.

Example:

```
01  OIL & GAS
    Improving → Leading
    Stable → Broadening
    Breadth +18pp

02  COAL
    Leading
    Broadening → Narrowing
    Breadth −28pp

03  HEALTHCARE
    Lagging → Improving
    Breadth +17pp
```

This composition should replace the current first row of four equal cards.

---

# 26. MATERIAL SHIFT ITEM

Do NOT use a large independent card for every shift.

Use dense editorial rows.

Structure:

```
01
OIL & GAS

IMPROVING → LEADING
STABLE → BROADENING

+7.4% excess
72% breadth
```

Use thin separators.

Selected row may expand slightly.

Click → Group Explorer.

---

# 27. LEADERSHIP MAP VISUAL IDENTITY

This is the product's signature visualization.

Four logical states:

```
IMPROVING             LEADING


LAGGING               WEAKENING
```

Do not make quadrants brightly colored.

Use very subtle background tint.

Plot trajectories.

Current dot:

solid.

Historical trail:

progressively fading.

Selected group:

Signal Orange ring.

---

# 28. SECOND VIEWPORT — LEADERSHIP TAPE

Create:

# Leadership Tape

Dense full-width institutional table.

Columns:

```
Rank
Group
Lead
Diff
20D Excess
60D Excess
Breadth
Δ Breadth
Concentration
Persistence
Confirmation
```

Make it feel like a professional market monitor.

Features:

* sticky header,
* compact rows,
* subtle hover,
* sortable columns,
* tiny inline sparkline where useful,
* row click → Explorer.

Use background tint sparingly to show states.

---

# 29. TABLE VISUAL LANGUAGE

Do NOT wrap every row in cards.

Use proper table density.

State example:

```
1  Oil & Gas        LEADING    BROADENING   +7.4   +11.2   72   +18   44   4W
2  Banks            LEADING    STABLE       +5.9    +8.1   64    +2   51   7W
3  Coal             LEADING    NARROWING    +8.1   +12.4   48   −28   69   9W
```

Numbers aligned right.

Use tabular figures.

---

# 30. THIRD MODULE — UNDER THE SURFACE

Create a visually rich full-width analysis module.

Headline:

# Under the Surface

Select one interesting group automatically:

`Oil & Gas`

Split:

### Left

Breadth history chart.

### Center

Constituent participation matrix.

Example:

```
          W-4  W-3  W-2  NOW
MEDC       ●    ●    ●    ●
ELSA       ○    ●    ●    ●
AKRA       ○    ○    ●    ●
...
```

### Right

Evidence stack:

```
Leadership      LEADING
Diffusion       BROADENING
Persistence     4W

Fundamentals    SUPPORTIVE
Foreign Flow    CONFIRMING

Contradiction
Concentration remains moderate
```

This section should demonstrate the product's analytical depth.

---

# 31. FOURTH MODULE — BROAD VS NARROW

Add a comparative visualization:

# Same Strength. Different Structure.

Two groups shown side by side.

Example:

```
OIL & GAS
+7.4%

████████░░ Breadth 72%
Top-3 44%

BROADENING
```

versus:

```
COAL
+8.1%

████░░░░░░ Breadth 48%
Top-3 69%

NARROWING
```

This visually reinforces the product's differentiation.

---

# 32. OPTIONAL MARKET HEATMAP

Do NOT use a generic performance heatmap.

Create a custom:

# Diffusion Map

Sector → Industry → constituent treemap.

Size:

free-float market cap or market cap.

Color:

**relative leadership**, not daily return.

Border / secondary indicator:

diffusion state.

Allow:

```
Size by: Market Cap / Equal
Color by: Leadership / Breadth
```

Inspired by market-map interaction principles, not appearance.

---

# =====================================================

# GROUP EXPLORER

# =====================================================

# 33. GROUP EXPLORER HEADER

Design like an institutional security / strategy tear sheet.

Breadcrumb:

```
IDX / ENERGY / OIL & GAS
```

Title:

# Oil & Gas

Status line:

```
LEADING · BROADENING · 4W PERSISTENCE
```

One-line read:

> Relative strength remains positive while participation continues to expand across eligible constituents.

---

# 34. GROUP EXPLORER MAIN GRID

Do not use four equal metric cards.

Use:

### Left 70%

Large multi-panel chart area.

Tabs:

```
Leadership
Breadth
Constituents
```

### Right 30%

Sticky evidence panel.

```
STATE

Leadership      LEADING
Diffusion       BROADENING
Persistence     4W

CONFIRMATION

Fundamentals    SUPPORTIVE
Foreign Flow    CONFIRMING

CONTRADICTION

Top-3 concentration remains elevated.
```

---

# 35. CHART SYSTEM

Create a consistent chart language.

No heavy chart borders.

Use:

* soft grid lines,
* small labels,
* clear zero lines,
* Signal Orange for selected point,
* semantic colors only for state interpretation.

Possible charts:

### Relative Strength

group vs IHSG.

### Breadth

outperforming constituent percentage.

### Concentration

top contributors.

### Leadership trajectory

position over time.

---

# 36. CONSTITUENT TABLE

Make this dense and serious.

Columns:

```
Ticker
Company
20D
Excess
60D Excess
Participation
Contribution
Foreign Flow
```

Use ticker as bold primary anchor.

Avoid stock logos.

Avoid consumer-fintech styling.

---

# =====================================================

# METHODOLOGY

# =====================================================

# 37. METHODOLOGY PAGE

Make it resemble a modern quantitative research notebook / institutional methodology sheet.

Use a narrower content column.

Sections:

```
01 Universe
02 Benchmark
03 Leadership
04 Breadth
05 Diffusion
06 Concentration
07 Persistence
08 Confirmation
09 Data Quality
10 Limitations
```

Use formulas.

Use small diagrams.

Use version metadata.

---

# 38. DATA PROVENANCE PANEL

Dark terminal-like strip:

```
SOURCE          SECTORS
MARKET          IDX
AS OF           26 AUG 2026
METHOD          leadership-v0.3
DIFFUSION       diffusion-v0.3
UNIVERSE        eligibility-v0.2
```

---

# =====================================================

# ALTERNATIVE HOME CONCEPTS

# =====================================================

# 39. CREATE THREE APP HOMEPAGE CONCEPTS

Before finalizing the design, create three different high-level variants.

Do not merely change colors.

---

## CONCEPT A — COMMAND CENTER

Most institutional.

First viewport:

```
Market Read
Leadership Map + Material Shifts
Leadership Tape
```

Characteristics:

* dense,
* chart-led,
* Koyfin-like information hierarchy,
* strong for repeated daily use.

---

## CONCEPT B — EDITORIAL INTELLIGENCE

More distinctive for hackathon presentation.

First viewport:

Large narrative:

# Leadership is broadening beneath IDX.

Below:

```
2 NEW LEADERS
3 BROADENING
2 NARROWING
```

Then one large highlighted market story:

```
OIL & GAS
Improving → Leading
```

with chart.

Material shifts appear as editorial research headlines.

Characteristics:

* more storytelling,
* more memorable,
* better for demo.

---

## CONCEPT C — MAP FIRST

The entire first viewport is dominated by:

# Leadership Map

with floating analytical side panels.

Below:

```
What Changed
Leadership Tape
Under the Surface
```

Characteristics:

* visually strongest,
* immediately differentiated,
* product identity centered on market rotation.

---

# 40. RECOMMENDED FINAL COMPOSITION

After creating all three concepts, combine:

**Concept A's information density**

*

**Concept B's narrative Market Read**

*

**Concept C's large signature Leadership Map**

into one final homepage.

Do not simply choose the safest concept.

---

# 41. INTERACTIONS

Prototype these flows.

### Flow 1

Homepage:

click Oil & Gas material shift

→ Group Explorer.

### Flow 2

Leadership Map:

hover point

→ detailed tooltip.

Click point

→ side evidence drawer.

Click:

`Open group`

→ Group Explorer.

### Flow 3

Leadership Tape:

sort by:

`Δ Breadth`

→ rank updates.

### Flow 4

Taxonomy:

`Sector → Industry`

→ map and table transition.

---

# 42. HOVER TOOLTIP

Example:

```
OIL & GAS

Leadership       LEADING
Diffusion        BROADENING

20D Excess       +7.4%
60D Excess      +11.2%
Breadth             72%
Δ Breadth          +18pp
Top-3                44%
```

Compact and analytical.

---

# 43. MICRO-INTERACTIONS

Use restrained motion.

Examples:

* trajectory draws when map loads,
* table ranks subtly shift after taxonomy change,
* breadth bars animate from previous to current,
* evidence drawer slides in,
* selected bubble receives an orange ring.

No flashy page transitions.

---

# 44. VISUAL DENSITY

Use approximately:

* 12–14 px body data,
* 14–16 px section labels,
* 24–32 px major headers,
* 36–44 px only for public homepage hero.

The in-app product should remain dense.

---

# 45. CARD RULE

Only use a card when the item is an independent analytical object.

Good:

* Market Read,
* selected evidence drawer,
* public homepage product preview.

Bad:

* one card per tiny metric,
* one card per table row,
* cards inside cards inside cards.

Prefer:

* sections,
* rows,
* split panels,
* tables,
* chart regions,
* dividers.

---

# 46. VISUAL SIGNATURE

Develop three recurring brand motifs:

### 1. Trajectory line

Represents leadership migration.

### 2. Constituent dot matrix

Represents diffusion.

### 3. Orange current-position marker

Represents “where the signal is now.”

Use these consistently across marketing and product UI.

This should make IDX Leadership Diffusion recognizable even without the logo.

---

# 47. LOGO

Refine the current simple triangle symbol.

Keep it geometric and restrained.

Possible concept:

a small triangular/arrow form built from:

* one leading point,
* several trailing constituent points.

Do NOT create a complex finance logo.

Wordmark:

**IDX Leadership**

small mono second line:

`DIFFUSION`

---

# 48. DO NOT ADD

No:

* chatbot,
* buy/sell buttons,
* price targets,
* recommendation badges,
* portfolio page,
* alerts page,
* news feed as primary module,
* broker terminal,
* candlestick-heavy dashboard,
* generic KPI-card wall,
* giant gradients,
* glassmorphism,
* neon green,
* crypto aesthetic.

---

# 49. COPY LANGUAGE

Use short institutional copy.

Good:

> Leadership strengthened while participation broadened.

> Headline strength remains intact, but fewer constituents are participating.

> Relative performance is improving, although medium-term leadership remains negative.

Bad:

> Huge opportunity!

> Extremely bullish!

> Strong buy signal!

> AI has detected...

---

# 50. DESIGN SYSTEM DELIVERABLE

Create:

### Foundations

* colors,
* typography,
* spacing,
* grid,
* radius,
* shadows,
* chart colors.

### Components

* sidebar,
* market bar,
* state chip,
* diffusion chip,
* transition row,
* evidence row,
* data status,
* table,
* tooltip,
* evidence drawer,
* chart legend,
* filter control,
* empty state,
* stale state,
* data gap.

---

# 51. FIGMA PAGES

Create:

### 00 — Design System

### 01 — Public Homepage

### 02 — App Homepage Concepts

* Command Center
* Editorial Intelligence
* Map First

### 03 — Final App Homepage

### 04 — Leadership Map

### 05 — Group Explorer

### 06 — Methodology & Data Quality

### 07 — States & Responsive

---

# 52. MOCK DATA

Use realistic Indonesian examples such as:

```
Oil & Gas
Coal
Banks
Telecommunications
Healthcare
Basic Materials
Infrastructure
Property
Technology
Consumer
```

Tickers:

```
BBCA
BBRI
BMRI
BBNI
TLKM
ISAT
MEDC
ELSA
AKRA
ANTM
INCO
```

Use realistic-looking illustrative values.

Clearly treat all numbers as design mock data.

---

# 53. FINAL QUALITY TEST

Before finishing, ask:

### Can someone understand the product in five seconds?

They should see:

> market leadership + participation.

### Can someone understand what changed in ten seconds?

They should see:

> ranked material transitions.

### Can someone investigate why within thirty seconds?

They should reach:

> breadth + concentration + constituents + confirmation + contradiction.

If not, redesign.

---

# 54. FINAL PRINCIPLE

The defining insight of this product is:

> **A market move can be strong but unhealthy.**

The UI should make these two conditions look immediately different:

### LEADING + BROADENING

and

### LEADING + NARROWING

Do not merely show them as two tiny status pills.

Make that contrast the visual identity of the entire product.
