#!/usr/bin/env python3
"""Weekly discovery pass: collect, qualify, deduplicate, and publish opportunities."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from collections import Counter

from discovery_pipeline import collect_sources, merge_opportunities
from opportunity_utils import DATA_FILE, ROOT, STATE_FILE, fetch, load_json, qualifies, save_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sources = load_json(ROOT / "config" / "sources.json", [])
    existing = load_json(DATA_FILE, [])
    disabled_source_ids = {source["id"] for source in sources if not source.get("enabled", True)}
    retained_existing = []
    removed_reasons: Counter[str] = Counter()
    for item in existing:
        if item.get("sourceId") in disabled_source_ids:
            removed_reasons["source disabled"] += 1
            continue
        allowed, reason = qualifies(item)
        if allowed:
            retained_existing.append(item)
        else:
            removed_reasons[reason] += 1
    discovered = []
    source_results = collect_sources(sources, fetch)
    for result in source_results:
        discovered.extend(result.items)
        print(f"  {result.source_id}: {result.accepted} accepted, {result.rejected} rejected, {len(result.failures)} warnings")

    combined = merge_opportunities(retained_existing, discovered)
    failures = [failure | {"source": result.source_id} for result in source_results for failure in result.failures]
    report = {
        "mode": "discovery",
        "ranAt": datetime.now(timezone.utc).isoformat(),
        "newCount": max(0, len(combined) - len(existing)),
        "removedCount": len(existing) - len(retained_existing),
        "removedReasons": dict(sorted(removed_reasons.items())),
        "sourceCount": len(source_results),
        "fetchedCount": sum(result.fetched for result in source_results),
        "parsedCount": sum(result.parsed for result in source_results),
        "acceptedCount": sum(result.accepted for result in source_results),
        "rejectedCount": sum(result.rejected for result in source_results),
        "failureCount": len(failures),
        "failures": failures[:25],
        "sources": [result.as_dict() for result in source_results],
    }
    if not args.dry_run:
        save_json(DATA_FILE, combined)
        save_json(STATE_FILE, report)
    print(f"NextUp PNW discovery: {report['newCount']} new, {report['acceptedCount']} accepted, {report['rejectedCount']} rejected, {len(failures)} source warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
