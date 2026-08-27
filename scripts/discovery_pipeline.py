#!/usr/bin/env python3
"""Testable source collection, qualification, reporting, and deterministic merge."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable
import urllib.parse

from opportunity_utils import PNW_REGIONS, canonical_url, clean_text, dedupe_key, display_identity_key, event_links, external_event_keys, pnw_region, qualifies, schema_to_opportunity, syndication_key, unique_opportunity_id
from source_adapters import extract_records

Fetcher = Callable[[str], tuple[str, str]]
SOURCE_CITY_HINTS = {
    "uw-campus-calendar": "Seattle",
    "uw-bothell-calendar": "Bothell",
    "uw-tacoma-calendar": "Tacoma",
    "seattle-u-events": "Seattle",
    "oregon-state-events": "Corvallis",
    "university-oregon-events": "Eugene",
    "boise-state-events": "Boise",
    "ubc-vancouver-events": "Vancouver",
    "ubc-okanagan-events": "Kelowna",
}
PNW_REGION_ORDER = ("WA", "OR", "ID", "BC")


def _series_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("title", "")).casefold(), str(item.get("organizer", "")).casefold())


@dataclass
class SourceResult:
    source_id: str
    required: bool = False
    fetched: int = 0
    parsed: int = 0
    accepted: int = 0
    rejected: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    failures: list[dict[str, str]] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def health(self) -> str:
        if self.failures and self.parsed == 0 and self.fetched <= len(self.failures):
            return "failed"
        if self.failures:
            return "degraded"
        if self.parsed == 0:
            return "empty"
        return "healthy"

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_id,
            "health": self.health,
            "required": self.required,
            "fetched": self.fetched,
            "parsed": self.parsed,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "rejectionReasons": self.rejection_reasons,
            "failureCount": len(self.failures),
            "failures": self.failures[:5],
        }


def _source_endpoints(source: dict[str, Any]) -> list[dict[str, str]]:
    configured = source.get("endpoints")
    if configured:
        values = configured
    elif source.get("feedUrls"):
        values = source["feedUrls"]
    elif source.get("feedUrl"):
        values = [source["feedUrl"]]
    else:
        values = [source["url"]]
    endpoints: list[dict[str, str]] = []
    for value in values:
        if isinstance(value, str):
            endpoints.append({"url": value, "adapter": str(source.get("adapter", "auto"))})
        elif isinstance(value, dict) and value.get("url"):
            endpoints.append({"url": str(value["url"]), "adapter": str(value.get("adapter", source.get("adapter", "auto")))})
    return endpoints


def collect_source(source: dict[str, Any], fetcher: Fetcher, today: date | None = None) -> SourceResult:
    result = SourceResult(str(source["id"]), required=bool(source.get("required", True)))
    reasons: Counter[str] = Counter()
    series_counts: Counter[tuple[str, str]] = Counter()
    max_occurrences = max(1, int(source.get("maxOccurrences", 10)))
    known: set[str] = set()
    queue = _source_endpoints(source)
    crawled = False
    index = 0
    while index < len(queue):
        endpoint = queue[index]
        index += 1
        url = endpoint["url"]
        try:
            body, content_type = fetcher(url)
            result.fetched += 1
            records = extract_records(body, content_type, url, endpoint["adapter"])
            result.parsed += len(records)
            if source.get("crawl") and not crawled and "html" in content_type.lower():
                crawled = True
                limit = int(source.get("maxLinks", 8))
                queued_urls = {entry["url"] for entry in queue}
                queue.extend({"url": link, "adapter": "auto"} for link in event_links(body, url, limit) if link not in queued_urls)
            for record in records:
                if not record.get("organizer"):
                    record["organizer"] = source.get("name", "")
                item = schema_to_opportunity(
                    record,
                    str(source["url"]),
                    float(source.get("trust", 0.8)),
                    (today or date.today()).isoformat(),
                    region_hint=source.get("region"),
                    city_hint=source.get("city") or SOURCE_CITY_HINTS.get(str(source["id"])),
                )
                if not item:
                    result.rejected += 1
                    reasons["missing title or date"] += 1
                    continue
                item["sourceId"] = source["id"]
                allowed, reason = qualifies(item, today)
                key = dedupe_key(item)
                series_key = _series_key(item)
                if not allowed:
                    result.rejected += 1
                    reasons[reason] += 1
                elif key in known:
                    result.rejected += 1
                    reasons["duplicate within source"] += 1
                elif series_counts[series_key] >= max_occurrences:
                    result.rejected += 1
                    reasons["recurrence limit exceeded"] += 1
                else:
                    known.add(key)
                    series_counts[series_key] += 1
                    item.pop("_descriptionGenerated", None)
                    item.pop("_eventUrlPresent", None)
                    result.items.append(item)
        except Exception as exc:
            result.failures.append({"url": url, "error": str(exc)[:240]})
    result.accepted = len(result.items)
    result.rejection_reasons = dict(sorted(reasons.items()))
    return result


def collect_sources(sources: list[dict[str, Any]], fetcher: Fetcher, today: date | None = None, workers: int = 6) -> list[SourceResult]:
    """Collect independent sources concurrently while retaining config order."""
    enabled = [source for source in sources if source.get("enabled", True)]
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="nextup-source") as executor:
        futures = [executor.submit(collect_source, source, fetcher, today) for source in enabled]
        return [future.result() for future in futures]


def retain_existing(existing: list[dict[str, Any]], sources: list[dict[str, Any]], today: date | None = None) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Re-apply qualification and recurrence limits to already published records."""
    disabled = {str(source["id"]) for source in sources if not source.get("enabled", True)}
    limits = {str(source["id"]): max(1, int(source.get("maxOccurrences", 10))) for source in sources}
    occurrences: Counter[tuple[str, str]] = Counter()
    removed: Counter[str] = Counter()
    retained: list[dict[str, Any]] = []
    for original in existing:
        item = dict(original)
        for key in ("title", "organizer", "description", "venue", "city", "eligibility", "whyItStandsOut", "cost", "type", "field", "format", "skillLevel"):
            if key in item:
                item[key] = clean_text(item[key])
        if not item.get("region"):
            region_text = " ".join(clean_text(item.get(key)) for key in ("title", "organizer", "description", "venue", "city", "sourceUrl"))
            item["region"] = pnw_region(region_text)
        source_id = str(item.get("sourceId", ""))
        if item.get("city") in {*PNW_REGIONS.values(), "Pacific Northwest"}:
            item["city"] = "Online" if item.get("format") == "Online" else SOURCE_CITY_HINTS.get(source_id, "Location TBD")
        if source_id in disabled:
            removed["source disabled"] += 1
            continue
        allowed, reason = qualifies(item, today)
        if not allowed:
            removed[reason] += 1
            continue
        series_key = _series_key(item)
        if occurrences[series_key] >= limits.get(source_id, 10):
            removed["recurrence limit exceeded"] += 1
            continue
        occurrences[series_key] += 1
        retained.append(item)
    return retained, removed


def _identity_keys(item: dict[str, Any]) -> tuple[str, ...]:
    keys = ["event:" + dedupe_key(item), "display:" + display_identity_key(item), *("external:" + key for key in external_event_keys(item))]
    url = canonical_url(item.get("registrationUrl"))
    parsed = urllib.parse.urlparse(url)
    if url and parsed.scheme in {"http", "https"} and parsed.hostname:
        keys.append(f"url:{url}:{item.get('startDate', '')}")
    return tuple(keys)


def _match_position(item: dict[str, Any], index: dict[str, int], merged: list[dict[str, Any]]) -> int | None:
    exact = next((index[key] for key in _identity_keys(item) if key in index), None)
    if exact is not None:
        return exact
    candidate_host = urllib.parse.urlparse(canonical_url(item.get("registrationUrl"))).hostname
    if not candidate_host:
        return None
    mirror_key = syndication_key(item)
    for position, existing in enumerate(merged):
        existing_host = urllib.parse.urlparse(canonical_url(existing.get("registrationUrl"))).hostname
        if existing_host and existing_host != candidate_host and syndication_key(existing) == mirror_key:
            return position
    return None


def _merged_record(existing: dict[str, Any], discovered: dict[str, Any]) -> dict[str, Any]:
    existing_confidence = float(existing.get("confidence", 0))
    discovered_confidence = float(discovered.get("confidence", 0))
    primary, secondary = (discovered, existing) if discovered_confidence >= existing_confidence else (existing, discovered)
    merged = dict(secondary)
    merged.update({key: value for key, value in primary.items() if value not in (None, "", [], {})})
    merged["id"] = existing["id"]
    return merged


def merge_opportunities(existing: list[dict[str, Any]], discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_existing = []
    for value in existing:
        item = dict(value)
        if not item.get("registrationUrl"):
            item["registrationUrl"] = item.get("sourceUrl")
        normalized_existing.append(item)
    merged: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    for item in normalized_existing:
        match = _match_position(item, index, merged)
        if match is not None:
            merged[match] = _merged_record(merged[match], item)
            continue
        position = len(merged)
        merged.append(item)
        for key in _identity_keys(item):
            index[key] = position
    used_ids = {str(item.get("id")) for item in merged if item.get("id")}
    for candidate in discovered:
        match = _match_position(candidate, index, merged)
        if match is not None:
            merged[match] = _merged_record(merged[match], candidate)
            for key in _identity_keys(merged[match]):
                index[key] = match
            continue
        item = dict(candidate)
        item["id"] = unique_opportunity_id(item, used_ids)
        used_ids.add(item["id"])
        position = len(merged)
        merged.append(item)
        for key in _identity_keys(item):
            index[key] = position
    return sorted(merged, key=lambda item: (item.get("startDate", "9999-99-99"), item.get("title", ""), item.get("id", "")))


def limit_opportunities(items: list[dict[str, Any]], maximum: int = 500, minimum_per_region: int = 50) -> list[dict[str, Any]]:
    """Bound generated-site size while reserving meaningful coverage in every PNW region."""
    ordered = sorted(items, key=lambda item: (item.get("startDate", "9999-99-99"), item.get("title", ""), item.get("id", "")))
    if len(ordered) <= maximum:
        return ordered
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for region in PNW_REGION_ORDER:
        for item in (candidate for candidate in ordered if candidate.get("region") == region):
            if sum(candidate.get("region") == region for candidate in selected) >= minimum_per_region:
                break
            selected.append(item)
            selected_ids.add(str(item.get("id")))
    for item in ordered:
        if len(selected) >= maximum:
            break
        if str(item.get("id")) not in selected_ids:
            selected.append(item)
            selected_ids.add(str(item.get("id")))
    return sorted(selected, key=lambda item: (item.get("startDate", "9999-99-99"), item.get("title", ""), item.get("id", "")))
