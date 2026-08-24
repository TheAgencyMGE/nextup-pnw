#!/usr/bin/env python3
"""Daily link and expiry verification for published opportunities."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from opportunity_utils import ARCHIVE_FILE, DATA_FILE, STATE_FILE, fetch, iso_date, load_json, save_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    today = date.today().isoformat()
    current, archive = [], load_json(ARCHIVE_FILE, [])
    warnings, checked = [], 0
    for item in load_json(DATA_FILE, []):
        end = iso_date(item.get("endDate")) or iso_date(item.get("startDate"))
        deadline = iso_date(item.get("deadline"))
        if (end and end < today) or (deadline and deadline < today and item.get("status") == "open"):
            item["status"] = "closed"
            item["archivedAt"] = today
            archive.append(item)
            continue
        try:
            fetch(item.get("sourceUrl") or item.get("registrationUrl"))
            item["verifiedAt"] = today
            checked += 1
        except Exception as exc:
            warnings.append({"id": item.get("id"), "error": str(exc)[:240]})
        current.append(item)
    report = {"mode": "verification", "ranAt": datetime.now(timezone.utc).isoformat(), "checkedCount": checked, "activeCount": len(current), "archivedCount": len(archive), "warningCount": len(warnings), "warnings": warnings[:25]}
    if not args.dry_run:
        save_json(DATA_FILE, current)
        save_json(ARCHIVE_FILE, archive)
        save_json(STATE_FILE, report)
    print(f"NextUp PNW verification: {checked} checked, {len(warnings)} warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
