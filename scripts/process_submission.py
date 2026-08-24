#!/usr/bin/env python3
"""Validate one GitHub Issue Form submission and publish only high-confidence events."""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

from opportunity_utils import DATA_FILE, city_from, classify_field, classify_type, clean_text, dedupe_key, extract_jsonld, fetch, load_json, qualifies, save_json, schema_to_opportunity, slugify, unique_opportunity_id

RESULT_FILE = Path(os.getenv("SUBMISSION_RESULT", "submission-result.json"))


def fields(body: str) -> dict[str, str]:
    chunks = re.split(r"\n###\s+", "\n" + body)
    result: dict[str, str] = {}
    for chunk in chunks[1:]:
        title, _, value = chunk.partition("\n")
        result[title.strip().lower()] = value.strip().split("\n### ", 1)[0].strip()
    return result


def finish(status: str, message: str, item_id: str | None = None) -> int:
    save_json(RESULT_FILE, {"status": status, "message": message, "itemId": item_id})
    print(message)
    return 0


def main() -> int:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        return finish("error", "No GitHub event payload was provided.")
    payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    issue = payload.get("issue", {})
    submitted = fields(issue.get("body", ""))
    url = next((value for key, value in submitted.items() if "official" in key and "link" in key), "")
    match = re.search(r"https?://[^\s<>]+", url)
    if not match:
        return finish("rejected", "We couldn't find a valid official URL in this submission. Please edit the issue and add one.")
    url = match.group(0).rstrip(".,)")
    try:
        page, _ = fetch(url)
    except Exception as exc:
        return finish("needs_review", f"The official page could not be verified automatically yet: {str(exc)[:160]}")
    candidates = []
    for schema in extract_jsonld(page):
        item = schema_to_opportunity(schema, url, 0.90)
        if item and item.get("endDate", "") >= date.today().isoformat():
            candidates.append(item)
    if not candidates:
        supplied_dates = re.findall(r"20\d{2}-\d{2}-\d{2}", submitted.get("event date or deadline", ""))
        title = clean_text(submitted.get("opportunity name", ""))
        location = clean_text(submitted.get("location", ""))
        eligibility = clean_text(submitted.get("who can participate?", "")) or "See the official page for eligibility"
        reason = clean_text(submitted.get("why should students know about it?", ""))
        page_text = clean_text(page).lower()
        meaningful_title_words = [word for word in re.findall(r"[a-z0-9]{4,}", title.lower()) if word not in {"2026", "2027", "event", "program"}]
        if not title or not supplied_dates or not meaningful_title_words or not any(word in page_text for word in meaningful_title_words):
            return finish("needs_review", "The official link works, but the submitted details could not be matched confidently enough for automatic publication.")
        start = supplied_dates[0]
        end = supplied_dates[1] if len(supplied_dates) > 1 else start
        if end < date.today().isoformat():
            return finish("rejected", "The submitted date has already passed.")
        submitted_field = clean_text(submitted.get("career field", ""))
        submitted_type = clean_text(submitted.get("opportunity type", ""))
        combined = f"{title} {submitted_field} {submitted_type} {eligibility} {reason}"
        field = submitted_field if submitted_field and submitted_field != "Cross-disciplinary" else classify_field(combined)
        candidates.append({
            "id": f"{slugify(title)}-{start[:4]}", "title": title, "organizer": "Community-submitted official source",
            "field": field, "type": classify_type(submitted_type), "format": "Online" if "online" in location.lower() else ("Hybrid" if "hybrid" in location.lower() else "In person"),
            "city": city_from(location), "venue": location, "startDate": start, "endDate": end, "deadline": None,
            "status": "announced", "cost": "See official page", "eligibility": eligibility, "skillLevel": "Not stated",
            "beginnerFriendly": any(word in combined.lower() for word in ("beginner", "all skill", "no experience")),
            "description": reason or f"A community-submitted {classify_type(submitted_type).lower()} verified against the organizer's official page.",
            "whyItStandsOut": reason or "A local opportunity submitted by the community and matched to an official source.",
            "sourceUrl": url, "registrationUrl": url, "verifiedAt": date.today().isoformat(),
            "tags": [field.lower(), classify_type(submitted_type).lower(), city_from(location).lower()], "confidence": 0.90,
        })
    title_hint = submitted.get("opportunity name", "").lower()
    candidates.sort(key=lambda item: (title_hint not in item["title"].lower(), item["startDate"]))
    item = candidates[0]
    allowed, reason = qualifies(item)
    if not allowed:
        return finish("rejected", f"The resource was checked but wasn't auto-published: {reason}.")
    current = load_json(DATA_FILE, [])
    keys = {dedupe_key(existing) for existing in current}
    if dedupe_key(item) in keys:
        return finish("duplicate", "This opportunity is already in NextUp PNW.", item["id"])
    item["id"] = unique_opportunity_id(item, {existing["id"] for existing in current})
    current.append(item)
    current.sort(key=lambda value: (value.get("startDate", "9999"), value.get("title", "")))
    save_json(DATA_FILE, current)
    return finish("accepted", f"Verified and published **{item['title']}**. Thanks for helping students find it in time!", item["id"])


if __name__ == "__main__":
    raise SystemExit(main())