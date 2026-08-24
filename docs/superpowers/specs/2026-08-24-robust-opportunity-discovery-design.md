# Robust Opportunity Discovery Design

## Goal

Turn NextUp PNW's discovery job into a dependable, observable ingestion pipeline that publishes at least 100 currently actionable Puget Sound opportunities from official sources without padding the directory with generic events.

## Scope and success criteria

- Ingest JSON-LD events, RSS/Atom entries, iCalendar events, structured JSON feeds, and conservative HTML event metadata.
- Prefer official organizer pages and public official feeds. Do not bypass access controls or robots.txt.
- Publish only listings with a usable title, future end/start date, official URL, relevant opportunity intent, and PNW connection (or a locally relevant online program).
- Keep stable IDs across refreshes and prevent duplicate listings across sources and recurring calendar URLs.
- Produce per-source counts for fetched, parsed, accepted, rejected, and failed records, including bounded diagnostic reasons.
- Refresh the generated site with at least 100 active, individually actionable listings when official sources provide enough valid records.
- Remain dependency-free under Python 3.11+ so the existing GitHub Actions workflow stays simple.

## Architecture

Discovery remains a batch pipeline driven by `config/sources.json`. Each source may declare one or more collection endpoints and an adapter hint. The collector fetches an endpoint once, selects an extractor from its content and configuration, normalizes extracted records into the existing opportunity schema, applies quality rules, merges duplicates, and writes a deterministic result.

Extraction is separated from policy. Format adapters only recover structured records. Normalization resolves dates, locations, organizers, URLs, status, cost, eligibility, and classifications. Qualification then enforces freshness, PNW relevance, opportunity relevance, source confidence, and required fields. This separation allows fixture-based tests without network access.

The supported adapter order is:

1. Structured JSON feeds and platform APIs.
2. JSON-LD embedded in HTML.
3. RSS/Atom feeds.
4. iCalendar feeds.
5. Conservative HTML metadata/cards for official pages that expose repeated event links and dates.

Source configuration can provide an explicit `adapter`, `feedUrl`, or `feedUrls`. Auto-detection remains available for ordinary pages. Platform-specific parsing is permitted only behind the common extractor interface.

## Data quality and deduplication

Normalization rejects records that lack a title, date, or official registration/detail URL. Online listings must still have a PNW organizer, audience, or source relationship; the word “online” alone is not sufficient geographic evidence.

Deduplication uses a normalized title, event date, organizer, and canonical URL. Tracking parameters, fragments, and inconsequential title punctuation/year differences are removed. When two records match, the higher-confidence record wins and missing fields are filled from the other record. Existing stable IDs are retained.

Broad public entertainment and passive attendance events are excluded unless they clearly provide career, education, competition, research, mentorship, leadership, volunteer, or skill-building value. Repeated sessions may remain separate only when their dates differ and each session is independently actionable.

## Refresh behavior and observability

The discovery command supports dry-run and normal write modes. Both print a source summary and final accepted/rejected/failure totals. The persisted `last-run.json` contains the same aggregate information plus bounded per-source diagnostics.

A failed source does not abort other sources. HTTP failures, malformed payloads, unsupported formats, and qualification failures are counted separately. Discovery exits nonzero only for a pipeline-level failure; individual source failures remain visible warnings.

Existing listings are merged with newly discovered records. Expired listings continue to be handled by verification. The static build is regenerated after a successful refresh.

## Source expansion

Coverage will be expanded using official municipal, county, library, college, university, museum, career-center, youth-program, and professional-organization sources across Seattle, Bellevue, Redmond, Kirkland, Renton, Bothell, Shoreline, Everett, Snohomish County, Tacoma, and Pierce County. Sources are selected for stable public feeds or well-structured official event pages and balanced across career fields.

## Testing and verification

Fixture tests cover every adapter, malformed input, URL resolution, date handling, online-region rules, deduplication/merge behavior, and per-source accounting. Network access is not required for unit tests. An integration-style test runs discovery against local fixture responses through injected fetch behavior.

Completion requires:

- All Python tests passing on Windows and the GitHub Actions target behavior remaining portable.
- The static builder completing successfully.
- Unique IDs and canonical duplicate keys across active data.
- No expired active records.
- At least 100 active records if the live official sources yield that many valid opportunities.
- A reviewed discovery report showing source successes and bounded failures.

