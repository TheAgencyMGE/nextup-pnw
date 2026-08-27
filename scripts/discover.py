#!/usr/bin/env python3
"""Weekly discovery pass: collect, qualify, deduplicate, and publish opportunities."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from discovery_pipeline import collect_sources, limit_opportunities, merge_opportunities, retain_existing
from opportunity_utils import DATA_FILE, ROOT, STATE_FILE, fetch, load_json, save_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sources = load_json(ROOT / "config" / "sources.json", [])
    existing = load_json(DATA_FILE, [])
    retained_existing, removed_reasons = retain_existing(existing, sources)
    discovered = []
    source_results = collect_sources(sources, fetch)
    for result in source_results:
        discovered.extend(result.items)
        print(f"  {result.source_id}: {result.accepted} accepted, {result.rejected} rejected, {len(result.failures)} warnings")

    combined = limit_opportunities(merge_opportunities(retained_existing, discovered))
    failures = [failure | {"source": result.source_id} for result in source_results for failure in result.failures]
    required_failures = [result.source_id for result in source_results if result.required and result.health == "failed"]
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
        "healthySourceCount": sum(result.health == "healthy" for result in source_results),
        "degradedSourceCount": sum(result.health == "degraded" for result in source_results),
        "emptySourceCount": sum(result.health == "empty" for result in source_results),
        "failedSourceCount": sum(result.health == "failed" for result in source_results),
        "requiredFailures": required_failures,
        "failures": failures[:25],
        "sources": [result.as_dict() for result in source_results],
    }
    if not args.dry_run:
        save_json(DATA_FILE, combined)
        save_json(STATE_FILE, report)
    print(f"NextUp PNW discovery: {report['newCount']} new, {report['acceptedCount']} accepted, {report['rejectedCount']} rejected, {len(failures)} source warnings")
    return 2 if required_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
