# Robust Opportunity Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a multi-format, observable opportunity collector that produces at least 100 active, verified PNW listings from official sources.

**Architecture:** Keep `discover.py` as the command entry point, move format parsing and merge policy into focused dependency-free modules, and drive platform endpoints through `sources.json`. Normalize every adapter's output through the existing opportunity schema before qualification and deterministic merge.

**Tech Stack:** Python 3.11+ standard library, `unittest`, JSON configuration, existing static-site builder.

**Spec:** `docs/superpowers/specs/2026-08-24-robust-opportunity-discovery-design.md`

## Global Constraints

- Official, public sources only; respect robots.txt and existing request throttling.
- Do not publish generic entertainment or passive-attendance filler.
- Every active listing requires a title, future date, official URL, opportunity relevance, and PNW relationship.
- Keep the Python collector dependency-free.
- Preserve stable IDs and prevent canonical duplicates.
- Persist bounded per-source diagnostics.

---

### Task 1: Portable baseline and quality-policy tests

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `scripts/build_static.py`
- Modify: `scripts/opportunity_utils.py`

**Interfaces:**
- Consumes: existing `date_label`, `qualifies`, `dedupe_key`, and URL fields.
- Produces: portable date labels, stricter online-region qualification, and canonical duplicate keys.

- [ ] Write failing tests proving Windows-safe date rendering, rejection of unrelated online events, canonical URL normalization, and organizer-aware duplicate behavior.
- [ ] Run the focused tests and confirm each fails for the intended missing behavior.
- [ ] Implement minimal portable formatting and policy helpers.
- [ ] Run the focused and complete Python suites.

### Task 2: Multi-format extraction adapters

**Files:**
- Create: `scripts/source_adapters.py`
- Create: `tests/fixtures/events.json`
- Create: `tests/fixtures/events.xml`
- Create: `tests/fixtures/events.ics`
- Create: `tests/fixtures/events.html`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `extract_records(body: str, content_type: str, source_url: str, adapter: str = "auto") -> list[dict]`.
- Records expose source-shaped values consumed by normalization: `name`, `description`, `startDate`, `endDate`, `location`, `url`, `organizer`, `offers`, and `eventStatus`.

- [ ] Add literal fixtures and failing tests for JSON arrays/platform wrappers, RSS/Atom, iCalendar, JSON-LD, and conservative HTML event cards.
- [ ] Run the adapter tests and verify expected failures.
- [ ] Implement adapter dispatch, URL resolution, XML parsing, iCalendar unfolding/escaping, and structured HTML extraction.
- [ ] Run adapter tests and refactor only after green.

### Task 3: Normalization, merge, and source accounting

**Files:**
- Create: `scripts/discovery_pipeline.py`
- Modify: `scripts/discover.py`
- Modify: `scripts/opportunity_utils.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `extract_records(...)`, `schema_to_opportunity(...)`, `qualifies(...)`.
- Produces: `collect_source(source: dict, fetcher: Callable) -> SourceResult`, `merge_opportunities(existing: list[dict], discovered: list[dict]) -> list[dict]`, and JSON-serializable source reports.

- [ ] Write failing tests for one-fetch endpoint processing, rejection counts, failure isolation, stable-ID preservation, duplicate field enrichment, and deterministic ordering.
- [ ] Run tests and verify failures identify the missing pipeline.
- [ ] Implement source endpoint expansion, collection, normalization, accounting, and merge behavior.
- [ ] Rewire `discover.py` to the tested pipeline while retaining `--dry-run`.
- [ ] Run focused tests and the whole suite.

### Task 4: Official source expansion

**Files:**
- Modify: `config/sources.json`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: source keys `id`, `name`, `url`, `adapter`, `feedUrl`/`feedUrls`, `trust`, `enabled`, and optional crawl settings.
- Produces: a geographically and topically balanced official-source catalog.

- [ ] Add a failing catalog validation test for unique IDs, HTTPS official URLs, valid trust/adapter values, and minimum geographic/category coverage.
- [ ] Verify the validation test fails against the current catalog.
- [ ] Add stable official feeds and program/event sources across the target PNW cities and fields.
- [ ] Run catalog and complete unit tests.

### Task 5: Live discovery and data audit

**Files:**
- Modify: `data/opportunities.json`
- Modify: `data/archive.json` when verification expires records.
- Modify: `data/last-run.json`

**Interfaces:**
- Consumes: live public endpoints from `config/sources.json`.
- Produces: refreshed canonical opportunity data and an auditable run report.

- [ ] Run verification to archive expired listings.
- [ ] Run discovery in dry-run mode and inspect accepted/rejected/failure counts by source.
- [ ] Correct only confirmed adapter/configuration issues, with a failing fixture test before code changes.
- [ ] Run discovery in write mode.
- [ ] Audit the output for active count, unique IDs/keys, required fields, date validity, official URLs, geography, field balance, and obvious generic-event false positives.
- [ ] Repeat targeted source/configuration improvements until at least 100 valid active listings are present or official-source availability is demonstrably exhausted.

### Task 6: Rebuild and final verification

**Files:**
- Modify: generated files under `docs/`
- Modify: `README.md` if source/listing counts are stated.

**Interfaces:**
- Consumes: refreshed `data/opportunities.json`.
- Produces: deployable static pages and an accurate project description.

- [ ] Run the static builder and rendered-HTML tests.
- [ ] Run all Python tests and lint/build checks available in the repository.
- [ ] Confirm generated detail-page count matches active data and no stale duplicate pages are linked.
- [ ] Review `git diff`, update stated counts, and record final verification evidence.

