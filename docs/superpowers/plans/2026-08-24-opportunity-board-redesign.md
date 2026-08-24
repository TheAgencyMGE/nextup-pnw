# NextUp PNW Opportunity Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the marketing-template interface with a schedule-first, accessible opportunity directory while preserving all data, routes, filters, SEO, and submission flows.

**Architecture:** Keep the existing React and static rendering paths. Align their semantic structure, use `app/globals.css` as the shared visual system, and regenerate `docs/` from the static templates and opportunity data.

**Tech Stack:** Next.js 16, React 19, TypeScript, dependency-free static templates, CSS, Node test runner, Python unittest.

**Spec:** `docs/superpowers/specs/2026-08-24-opportunity-board-redesign.md`

## Global Constraints

- Preserve all routes, filtering behavior, opportunity data, direct official links, metadata, and static generation.
- Do not add a remote font or visual-effect dependency.
- Support 1440, 1024, 768, 390, and 320 CSS pixels without horizontal overflow.
- Use factual, product-specific copy and no fabricated social proof.

---

### Task 1: Lock the new content contract

**Files:**
- Modify: `tests/rendered-html.test.mjs`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: current homepage and generated static HTML.
- Produces: assertions for the opportunity-board heading, specific actions, reset control, agenda structure, and absence of removed marketing patterns.

- [ ] Write assertions that fail against the current card-based interface.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Leave the failing tests in place for Tasks 2–4.

### Task 2: Recompose the React homepage

**Files:**
- Modify: `app/page.tsx`

**Interfaces:**
- Consumes: `data/opportunities.json` and existing filter state.
- Produces: `OpportunityRow`, directory toolbar, reset behavior, methodology strip, and submission section.

- [ ] Replace `OpportunityCard` with a chronological `OpportunityRow`.
- [ ] Add a labeled reset button that restores every filter.
- [ ] Replace marketing copy with approved factual copy.
- [ ] Preserve search, location, field, beginner-only filtering, and official links.

### Task 3: Align static rendering

**Files:**
- Modify: `static/index.template.html`
- Modify: `static/detail.template.html`
- Modify: `static/app.js`
- Modify: `scripts/build_static.py`

**Interfaces:**
- Consumes: static placeholder values and opportunity records.
- Produces: the same hierarchy and reset/filter behavior as React plus content-first detail pages.

- [ ] Replace the static hero, cards, and supporting sections with the approved structure.
- [ ] Generate agenda rows from Python with accessible labels and actions.
- [ ] Add static reset behavior and result summary announcements.
- [ ] Preserve canonical URLs, JSON-LD, metadata, and official links.

### Task 4: Build the shared visual system

**Files:**
- Modify: `app/globals.css`
- Modify: `app/layout.tsx`

**Interfaces:**
- Consumes: the semantic class names from Tasks 2–3.
- Produces: shared tokens, typography, schedule layout, detail layout, focus styles, and responsive behavior.

- [ ] Implement the approved token and typography system.
- [ ] Build the desktop agenda and detail layouts without card grids.
- [ ] Recompose filters and rows for 1024, 768, 390, and 320 pixels.
- [ ] Add visible focus, reduced-motion handling, and overflow guards.

### Task 5: Generate and verify

**Files:**
- Regenerate: `docs/index.html`
- Regenerate: `docs/opportunities/*/index.html`
- Regenerate: `docs/assets/styles.css`
- Regenerate: `docs/assets/app.js`

**Interfaces:**
- Consumes: completed templates, CSS, and data.
- Produces: deployable static output matching the React experience.

- [ ] Run `scripts/build_static.py` and confirm 111 pages are generated.
- [ ] Run Python tests, rendered-content tests where the app build is available, and ESLint.
- [ ] Test search, select, beginner, reset, empty state, and official-link affordances.
- [ ] Inspect home and detail pages at every required viewport and check overflow.
- [ ] Review copy and remove any remaining interchangeable marketing language.
- [ ] Commit the verified work to local `main` without pushing.

