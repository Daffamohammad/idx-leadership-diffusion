# IDX Leadership Diffusion — Figma Make UI/UX Master Prompt

Design a **high-fidelity interactive web application prototype** for a market-intelligence product called:

# IDX Leadership Diffusion

Tagline:

**See where market leadership is moving — and whether it is broadening or breaking beneath the surface.**

The application analyzes Indonesian equities and is intended for professional or analytically sophisticated users such as:

* equity researchers,
* portfolio managers,
* investment analysts,
* market strategists,
* research-oriented retail investors.

This is NOT a retail trading app.

It should feel like a compact **institutional market-intelligence workstation**.

---

# 1. PRODUCT PURPOSE

The system analyzes market leadership across:

```text
IDX Market
→ Sector
→ Subsector / Industry
→ Constituents
```

It tries to answer four primary questions:

### 1. Where is leadership?

Which groups are outperforming IHSG?

### 2. Is leadership changing?

Which groups are:

* improving,
* weakening,
* gaining leadership,
* losing leadership?

### 3. Is participation healthy?

Is leadership:

* broadening across constituents,
* stable,
* or narrowing into only a handful of stocks?

### 4. What supports or contradicts the signal?

Potential evidence layers include:

* relative market performance,
* constituent breadth,
* concentration,
* persistence,
* fundamentals,
* foreign flow,
* later optional broker/event confirmation.

The application should help users **prioritize research**, not tell them what to buy or sell.

---

# 2. CORE ANALYTICAL LANGUAGE

Keep these concepts visually separate.

Do NOT combine everything into one opaque score.

## Leadership

Possible states:

* LEADING
* IMPROVING
* LAGGING
* WEAKENING
* UNCONFIRMED

## Diffusion

Possible states:

* BROADENING
* STABLE
* NARROWING
* UNCONFIRMED

## Concentration

Indicates whether performance is driven by:

* broad participation,
* several leaders,
* or very few dominant constituents.

## Confirmation

Independent evidence such as:

* fundamentals,
* foreign flow,
* free-float-weighted participation.

Example:

```text
Oil & Gas

Leadership     LEADING
Diffusion      BROADENING
Concentration  MODERATE
Fundamentals   SUPPORTIVE
Foreign Flow   CONFIRMING
```

This evidence decomposition is central to the product.

---

# 3. DESIGN POSITIONING

Visually aim for:

**institutional research terminal × modern analytics SaaS × editorial financial research**

NOT:

* crypto exchange,
* Robinhood,
* flashy stock-trading platform,
* neon Bloomberg imitation,
* consumer fintech dashboard,
* generic AI SaaS,
* gamified investing app.

The design should feel:

* serious,
* analytical,
* calm,
* precise,
* information-dense,
* highly legible,
* contemporary,
* premium but understated.

Think:

> a tool an equity strategist could leave open on a second monitor all day.

---

# 4. IMPORTANT DIFFERENTIATION

Do not make the application primarily ticker-centric.

The hierarchy is:

```text
MARKET
   ↓
SECTOR
   ↓
INDUSTRY
   ↓
CONSTITUENTS
```

Individual stocks are supporting evidence for market leadership.

They are not the center of the application.

Avoid designing something that feels like a stock screener with a sector heatmap attached.

The product center is:

> **market leadership transition and diffusion.**

---

# 5. VISUAL THEME

Use **light mode only** for the main prototype.

Primary background:

```text
#F6F7F8 / warm near-white
```

Cards:

```text
#FFFFFF
```

Primary text:

```text
#17191C
```

Secondary text:

```text
#687078
```

Borders:

```text
#E4E7EA
```

Use subtle shadows only where useful.

Do not use floating glassmorphism.

Avoid excessive rounded corners.

Preferred radius:

```text
6–10 px
```

Use generous but efficient whitespace.

---

# 6. SEMANTIC COLORS

Use restrained analytical colors.

Suggested:

### Positive / improving

Muted teal:

```text
#167C72
```

### Leadership

Institutional blue:

```text
#315F8C
```

### Emerging / watch

Muted amber:

```text
#B7791F
```

### Deteriorating

Muted red:

```text
#B44949
```

### Neutral

Slate gray:

```text
#76818B
```

Do not turn the dashboard into a red-and-green heatmap.

Color should communicate hierarchy, not dominate it.

---

# 7. TYPOGRAPHY

Use a professional sans-serif.

Preferred:

* Inter,
* Geist,
* IBM Plex Sans,
* or similar.

Use tabular numbers wherever possible.

Typography hierarchy:

### Page title

28–32 px

### Section title

18–20 px

### Card headline metric

24–30 px

### Body

13–15 px

### Table

12–14 px

### Metadata

11–12 px

Avoid giant SaaS marketing headings inside the analytical product.

---

# 8. APPLICATION SHELL

Desktop-first.

Primary design width:

```text
1440 px
```

Also ensure usability around:

```text
1280 px
```

Application shell:

```text
┌──────────────────────────────────────────────────────────┐
│ Top application bar                                      │
├────────────┬─────────────────────────────────────────────┤
│            │                                             │
│ Sidebar    │ Main workspace                              │
│            │                                             │
│            │                                             │
└────────────┴─────────────────────────────────────────────┘
```

Sidebar width approximately:

```text
220–240 px
```

Keep sidebar compact.

---

# 9. SIDEBAR

Brand:

**IDX Leadership Diffusion**

Small descriptor:

**Market Intelligence**

Navigation:

1. **What Changed**
2. **Leadership Map**
3. **Group Explorer**
4. **Methodology**

At bottom:

```text
Data: Sectors
Market: Indonesia
Mode: Research
```

Include small data-status indicator.

Example:

```text
● READY
As of 26 Aug 2026
```

Do not overload sidebar with filters.

---

# 10. GLOBAL TOP BAR

Include:

### Market date

```text
As of 26 Aug 2026
```

### Taxonomy selector

```text
Sector
Industry
```

### Universe

```text
Eligible IDX
```

### Comparison

```text
vs 1W Ago
```

### Data status

```text
READY
READY WITH GAPS
STALE
```

Optional button:

```text
Refresh
```

Keep this area understated.

---

# 11. SCREEN 1 — WHAT CHANGED?

This is the product's primary screen.

The first viewport must answer:

> What materially changed in Indonesian market leadership?

Do NOT start with ten generic KPI cards.

---

# 12. WHAT CHANGED — HERO

Page heading:

# What Changed?

Subtitle:

**Material changes in IDX leadership, participation, and concentration.**

Small metadata:

```text
As of 26 Aug 2026 · Compared with previous observation
```

Immediately below, display:

```text
3 MATERIAL LEADERSHIP CHANGES
```

Then use compact but detailed transition cards.

---

# 13. TRANSITION CARD

Example card:

### Oil & Gas

```text
IMPROVING → LEADING
STABLE → BROADENING
```

Supporting evidence:

```text
20D excess return       +7.4%
Breadth                 54% → 72%
Leadership rank         #7 → #2
Top-3 concentration     44%
```

Short interpretation:

> Relative leadership strengthened while participation expanded across constituents.

Include:

```text
View evidence →
```

Second example:

### Coal

```text
LEADING
BROADENING → NARROWING
```

Evidence:

```text
20D excess return       +8.1%
Breadth                 76% → 48%
Top-3 concentration     69%
```

Interpretation:

> Headline leadership remains strong, but participation has narrowed materially.

This contrast is an important product concept.

---

# 14. TRANSITION CARD DESIGN

Cards should communicate:

```text
GROUP
STATE CHANGE
DIFFUSION CHANGE
KEY EVIDENCE
ONE-LINE INTERPRETATION
```

Do not use huge icons.

Use subtle direction arrows.

Examples:

```text
↑
↓
→
```

State chips should be restrained.

---

# 15. CURRENT MARKET LEADERSHIP SECTION

Below transition cards, create three columns:

### LEADING

Example:

```text
Oil & Gas
Telecommunications
Banks
```

### IMPROVING

```text
Healthcare
Infrastructure
Transportation
```

### WEAKENING

```text
Coal
Basic Materials
Property
```

For each group show:

```text
Leadership state
Diffusion state
Breadth
```

Do not show 15 metrics.

---

# 16. LEADERSHIP × DIFFUSION MATRIX

Add a major visualization.

X axis:

```text
Relative Leadership
Weak → Strong
```

Y axis:

```text
Diffusion
Narrowing → Broadening
```

Conceptual quadrants:

```text
             BROADENING

  EARLY RECOVERY       HEALTHY LEADERSHIP


  DETERIORATING        CONCENTRATED LEADERSHIP

             NARROWING
```

Plot sectors/industries as bubbles.

Bubble size may represent:

```text
eligible constituent count
```

or:

```text
free-float market capitalization
```

depending on data availability.

Tooltip:

```text
Group
Leadership state
20D excess return
60D excess return
Breadth
Breadth change
Concentration
```

Do not overload labels.

---

# 17. LEADERSHIP TABLE

Below visualization include a professional sortable table.

Columns:

```text
Group
Leadership
Diffusion
20D Excess
60D Excess
Breadth
Δ Breadth
Concentration
Persistence
```

Optional:

```text
Confirmation
```

Use compact status pills.

Example:

```text
Oil & Gas       LEADING      BROADENING
Coal            LEADING      NARROWING
Healthcare      IMPROVING    BROADENING
```

This table should look usable for actual research.

---

# 18. SCREEN 2 — LEADERSHIP MAP

Heading:

# Leadership Map

Subtitle:

**Cross-sectional position and trajectory of Indonesian market groups relative to IHSG.**

Primary visualization should dominate this screen.

---

# 19. LEADERSHIP MAP CHART

Use a large scatter / quadrant chart.

X-axis:

```text
Medium-horizon relative strength
```

For prototype:

```text
60D excess return vs IHSG
```

Y-axis:

```text
Short-horizon relative strength
```

or:

```text
20D relative momentum / acceleration
```

Quadrants:

```text
IMPROVING        LEADING

LAGGING          WEAKENING
```

Use faint quadrant backgrounds.

Do not use saturated background colors.

---

# 20. MAP TRAJECTORY

Allow optional:

```text
1W
4W
```

trails.

Current bubble should be emphasized.

Historical points should fade.

Use arrows subtly to indicate movement.

Example:

```text
Healthcare
      ○
       ○
        ● ↗
```

The chart should make rotation direction visually obvious without becoming messy.

---

# 21. DIFFUSION ENCODING

Do not encode everything with bubble color.

Suggested hierarchy:

### Bubble color

Leadership state.

### Bubble border

Diffusion:

```text
solid / stronger border = broadening
neutral border = stable
thin/dashed or muted = narrowing
```

Alternative:

Use a small adjacent diffusion icon.

Keep interpretability high.

---

# 22. MAP FILTER PANEL

Filters:

```text
Taxonomy level
Minimum eligible constituents
Leadership state
Diffusion state
```

Optional:

```text
Show only material changes
```

Do not build 20 filters.

---

# 23. MAP SIDE PANEL

When user clicks a group:

Open a right-side analytical drawer.

Example:

### Oil & Gas

```text
LEADING
BROADENING

20D excess        +7.4%
60D excess        +11.2%
Breadth             72%
Δ Breadth          +18pp
Concentration        44%
Persistence           4W
```

Buttons:

```text
Open Group Explorer
```

---

# 24. SCREEN 3 — GROUP EXPLORER

Heading:

# Group Explorer

Primary use:

Deep-dive one sector/industry.

Provide a search/select:

```text
Oil & Gas
```

Hierarchy breadcrumb:

```text
IDX → Energy → Oil & Gas
```

---

# 25. GROUP HERO

Design a clean research header.

Example:

# Oil & Gas

```text
Leadership      LEADING
Diffusion       BROADENING
Persistence     4 weeks
```

Underneath:

> Strong relative performance is being accompanied by increasingly broad constituent participation.

This sentence is generated from structured evidence.

Keep it concise.

---

# 26. EVIDENCE STRIP

Create four primary evidence cards:

### Relative Leadership

```text
+7.4%
20D vs IHSG
```

### Breadth

```text
72%
+18pp
```

### Concentration

```text
44%
Top-3 contribution
```

### Persistence

```text
4W
Current state
```

Do not label any metric:

```text
Conviction
Probability
Buy Score
```

---

# 27. BREADTH CHART

Create a time-series chart:

```text
Constituents outperforming IHSG (%)
```

Example:

```text
Week 1  38%
Week 2  47%
Week 3  59%
Week 4  72%
```

Overlay threshold/reference carefully if used.

Emphasize:

**Broadening participation**

---

# 28. PERFORMANCE VS PARTICIPATION

Create a two-line or combined analytical chart:

```text
Group relative performance
vs
Breadth
```

Purpose:

show whether:

```text
performance ↑ + breadth ↑
```

or:

```text
performance ↑ + breadth ↓
```

Do not use dual axes unless clearly labeled.

---

# 29. CONSTITUENT CONTRIBUTION

Create horizontal contribution bars.

Example:

```text
MEDC          18%
ELSA          13%
AKRA           9%
Other         60%
```

Show:

```text
Top-3 concentration
```

Clearly distinguish:

```text
leadership contribution
```

from:

```text
breadth participation
```

---

# 30. CONSTITUENT TABLE

Columns:

```text
Ticker
Company
20D Return
20D Excess
60D Excess
Participation
Contribution
Foreign Flow
```

Foreign flow may display:

```text
Confirming
Neutral
Against
Unavailable
```

Use ticker examples appropriate for Indonesian equities.

Use realistic but explicitly mock prototype data.

---

# 31. CONFIRMATION PANEL

Create a section:

# Confirmation

Split into:

### Fundamentals

Example:

```text
Revenue growth breadth     Positive
Earnings growth breadth    Improving
Profitability              Supportive
Report freshness           Current
```

Overall:

```text
SUPPORTIVE
```

### Foreign Flow

```text
Top leaders with net foreign buying    2 / 3
Flow trend                             Improving
```

Overall:

```text
CONFIRMING
```

These must look like independent evidence layers.

---

# 32. CONTRADICTORY EVIDENCE

Create an important panel:

# What Could Contradict This Signal?

Example:

```text
• Leadership remains moderately concentrated in the top three constituents.
• Medium-term relative strength has improved faster than fundamental breadth.
```

Use neutral warning styling.

Do not make it alarming.

This panel is important because the product should surface evidence against its own signal.

---

# 33. SCREEN INVALIDATION

Below contradiction:

# Screen Invalidation

Example:

```text
This leadership state would weaken if:

• 20D excess return turns negative;
• constituent breadth falls below 50%;
• diffusion shifts from broadening to narrowing.
```

Small footer:

```text
Screen-state invalidation, not an investment recommendation.
```

---

# 34. SCREEN 4 — METHODOLOGY & DATA QUALITY

Heading:

# Methodology & Data Quality

This should look serious and transparent.

Do not hide methodology behind tiny text.

---

# 35. DATA STATUS PANEL

Show:

```text
Core Market Data       READY
Taxonomy               READY
Benchmark              READY
Fundamentals           READY WITH GAPS
Foreign Flow           PARTIAL
Events                 OPTIONAL
```

As-of dates visible.

---

# 36. COVERAGE

Show:

```text
IDX listed securities       900+
Eligible securities         700+
Eligible industries          XX
Unconfirmed groups           XX
```

Use placeholder realistic values, clearly marked as prototype/demo.

Break exclusions into:

```text
insufficient history
stale trading
missing taxonomy
suspended
other
```

---

# 37. METHOD CARDS

Explain, concisely:

### Leadership

> Relative performance versus IHSG across short and medium horizons.

### Breadth

> Share of eligible constituents outperforming the benchmark.

### Diffusion

> Change in participation breadth between observations.

### Concentration

> Degree to which group leadership is dominated by a small number of constituents.

### Confirmation

> Independent fundamental and flow evidence.

---

# 38. METHODOLOGY FORMULAS

Display formulas professionally.

Example:

```text
20D Excess Return
= Security 20D Return − IHSG 20D Return
```

```text
Breadth
= Outperforming Constituents / Eligible Constituents
```

Do not make methodology intimidating.

Use expandable details.

---

# 39. PROVENANCE

Create a compact provenance table:

```text
Core Data Source        Sectors
Benchmark               IHSG
Method Version          leadership-v0.x
Diffusion Version       diffusion-v0.x
Snapshot Date           26 Aug 2026
```

Add:

```text
View full data methodology
```

---

# 40. DATA GAPS

Display explicit gaps.

Example:

```text
DATA GAP
Foreign-flow coverage incomplete for selected constituents.

DATA GAP
Free-float history unavailable for historical snapshots.
```

Use restrained amber.

Do not treat missing data as zero.

---

# 41. DESIGN SYSTEM PAGE

Create a Figma design-system section containing:

### Color tokens

### Typography

### Spacing

### Grid

### Status chips

### Evidence cards

### Transition cards

### Metric cards

### Table styles

### Tooltip

### Empty state

### Data-gap state

### Stale-data state

### Loading state

### Error state

---

# 42. COMPONENTS

Create reusable components:

```text
App Sidebar
Top Bar
Status Chip
Leadership Chip
Diffusion Chip
Metric Card
Transition Card
Evidence Card
Data Gap Card
Section Header
Filter Select
Search Field
Leadership Table
Constituent Table
Chart Tooltip
Group Drawer
Methodology Card
Data Status Row
```

Use variants.

---

# 43. STATUS CHIP SYSTEM

Leadership:

```text
LEADING
IMPROVING
WEAKENING
LAGGING
UNCONFIRMED
```

Diffusion:

```text
BROADENING
STABLE
NARROWING
UNCONFIRMED
```

Data:

```text
READY
READY WITH GAPS
PARTIAL
STALE
FAILED
```

Avoid excessive pill styling.

Make them compact.

---

# 44. EMPTY / ERROR STATES

Design states for:

### No eligible data

> No groups meet the current eligibility criteria.

### Data gap

> This confirmation layer is not available for the selected group.

### Stale

> Latest validated market snapshot is being shown.

### API failure

> Core Sectors market data could not be refreshed.

Do not insert fake results.

---

# 45. INTERACTION MODEL

Prototype interactions:

### From What Changed

Click group → Group Explorer.

### From Leadership Map

Click bubble → side drawer.

Side drawer → full Group Explorer.

### From table

Click row → Group Explorer.

### Taxonomy selector

Switch:

```text
Sector ↔ Industry
```

### Hover

Charts show structured analytical tooltips.

---

# 46. DO NOT ADD A CHATBOT

No:

```text
Ask AI
Chat with market
AI stock assistant
```

The product should demonstrate intelligence through structured market analysis.

If future AI exists, it should explain evidence rather than become the primary interface.

Do not design it now.

---

# 47. NO STOCK RECOMMENDATION LANGUAGE

Avoid:

* Buy
* Sell
* Strong Buy
* Target Price
* Upside
* Conviction
* Signal probability

Use:

* Leadership
* Improving
* Broadening
* Narrowing
* Confirmation
* Evidence
* Research Priority
* Material Change

---

# 48. NO BROKER TERMINAL

Do not make broker activity a major navigation item.

If displayed later, it belongs inside:

```text
Confirmation
```

or constituent drilldown.

The product should remain structurally different from ticker-centric flow-analysis platforms.

---

# 49. NO GENERIC HEATMAP AS HERO

A standard red/green sector heatmap is not the product.

If one exists at all, place it lower in hierarchy.

Primary visual identity should come from:

```text
leadership × diffusion
```

and:

```text
state transitions
```

---

# 50. INFORMATION DENSITY

Aim for roughly:

**institutional density, modern readability.**

Do not make every section a giant card.

Tables are acceptable and desirable.

Use borders and spacing more than shadows.

Charts should have:

* minimal gridlines,
* clear units,
* readable labels,
* restrained legends.

---

# 51. DEMO DATA

Use realistic Indonesian market labels.

Example groups:

```text
Banks
Telecommunications
Oil & Gas
Coal
Healthcare
Basic Materials
Infrastructure
Property
Transportation
Technology
Consumer
```

Example constituents:

```text
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

All numerical values should be treated as:

**representative mock data for design purposes.**

Do not imply the Figma prototype contains live market data.

---

# 52. HOMEPAGE STORY

The first screen should tell this story in under 10 seconds:

```text
WHAT CHANGED?
       ↓
WHERE IS LEADERSHIP?
       ↓
IS IT BROAD OR NARROW?
       ↓
WHAT IS DRIVING IT?
```

This is the product narrative.

---

# 53. VISUAL HIERARCHY PRIORITY

Priority:

```text
1. Material transitions
2. Leadership + diffusion
3. Breadth
4. Concentration
5. Constituents
6. Confirmation
7. Methodology
```

Do not reverse this hierarchy.

---

# 54. RESPONSIVE DESIGN

Primary:

```text
1440 desktop
```

Secondary:

```text
1280 laptop
```

Also create one responsive compact concept around:

```text
390–430 mobile
```

Mobile does not need every analytical visualization.

Prioritize:

* What Changed,
* group status,
* top evidence,
* constituent table transformed into cards.

Desktop remains the primary experience.

---

# 55. ACCESSIBILITY

Maintain sufficient contrast.

Do not rely solely on:

```text
green = good
red = bad
```

Always combine color with:

* label,
* icon,
* text,
* pattern/border where useful.

Charts must remain understandable for color-impaired users.

---

# 56. FINAL FIGMA DELIVERABLES

Create:

## Page 1 — Design System

Tokens + reusable components.

## Page 2 — What Changed

High-fidelity desktop.

## Page 3 — Leadership Map

High-fidelity desktop.

## Page 4 — Group Explorer

High-fidelity desktop.

## Page 5 — Methodology & Data Quality

High-fidelity desktop.

## Page 6 — Responsive / Key States

Include:

* mobile What Changed,
* empty state,
* data gap,
* stale state,
* loading state,
* error state.

---

# 57. PROTOTYPE FLOW

Connect:

```text
What Changed
    ↓
click Oil & Gas
    ↓
Group Explorer
```

and:

```text
Leadership Map
    ↓
click bubble
    ↓
side drawer
    ↓
Open Group Explorer
```

Also allow navigation via sidebar.

---

# 58. FINAL QUALITY BAR

The result should feel credible enough that a judge could reasonably believe:

> this is the frontend of a real institutional Indonesian equity market-intelligence tool.

But it should still feel:

* focused,
* distinctive,
* easy to demo,
* and achievable for a hackathon.

Do not design a fictional Bloomberg replacement.

---

# 59. FINAL DESIGN PRINCIPLE

The interface should visually reinforce the project's central idea:

> **Strong performance and healthy leadership are not the same thing.**

The design must make users immediately see the difference between:

```text
LEADING + BROADENING
```

and:

```text
LEADING + NARROWING
```

That distinction is the core visual and analytical identity of IDX Leadership Diffusion.
