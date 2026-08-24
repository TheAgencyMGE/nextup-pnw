#!/usr/bin/env python3
"""Weekly discovery pass: collect, qualify, deduplicate, and publish opportunities."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from opportunity_utils import DATA_FILE, ROOT, STATE_FILE, dedupe_key, event_links, extract_jsonld, fetch, load_json, qualifies, save_json, schema_to_opportunity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sources = load_json(ROOT / "config" / "sources.json", [])
    existing = load_json(DATA_FILE, [])
    known = {dedupe_key(item) for item in existing}
    discovered, failures = [], []

    for source in sources:
        if not source.get("enabled", True):
            continue
        urls = [source["url"]]
        try:
            page, _ = fetch(source["url"])
            if source.get("crawl"):
                urls.extend(event_links(page, source["url"], int(source.get("maxLinks", 8))))
        except Exception as exc:
            failures.append({"source": source["id"], "error": str(exc)[:240]})
            continue
        for index, url in enumerate(dict.fromkeys(urls)):
            try:
                body = page if index == 0 else fetch(url)[0]
                for schema in extract_jsonld(body):
                    item = schema_to_opportunity(schema, url, float(source.get("trust", 0.8)))
                    if not item:
                        continue
                    allowed, _ = qualifies(item)
                    key = dedupe_key(item)
                    if allowed and key not in known:
                        known.add(key)
                        discovered.append(item)
            except Exception as exc:
                failures.append({"source": source["id"], "url": url, "error": str(exc)[:240]})

    combined = sorted(existing + discovered, key=lambda item: (item.get("startDate", "9999"), item.get("title", "")))
    report = {"mode": "discovery", "ranAt": datetime.now(timezone.utc).isoformat(), "newCount": len(discovered), "sourceCount": len(sources), "failureCount": len(failures), "failures": failures[:25]}
    if not args.dry_run:
        save_json(DATA_FILE, combined)
        save_json(STATE_FILE, report)
    print(f"NextUp PNW discovery: {len(discovered)} new, {len(failures)} source warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
