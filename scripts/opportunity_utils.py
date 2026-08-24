#!/usr/bin/env python3
"""Shared, dependency-free utilities for the NextUp PNW data pipeline."""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "opportunities.json"
ARCHIVE_FILE = ROOT / "data" / "archive.json"
STATE_FILE = ROOT / "data" / "last-run.json"
USER_AGENT = "NextUpPNWBot/1.0 (+https://github.com/TheAgencyMGE/nextup-pnw; public-interest event index)"
REGION_WORDS = {"seattle", "bellevue", "bothell", "redmond", "everett", "tacoma", "kirkland", "renton", "shoreline", "lynnwood", "woodinville", "puget sound", "king county", "snohomish", "pierce county", "university of washington", "uw seattle", "uw bothell", "uw tacoma"}
OPPORTUNITY_WORDS = {"application", "apprenticeship", "art", "business", "career", "case competition", "civic", "clinical", "coding", "community service", "conference", "design", "designathon", "developer", "engineering", "entrepreneurship", "fair", "fellowship", "finance", "government", "hackathon", "health", "healthcare", "internship", "journalism", "lab", "law", "leadership", "maker", "marketing", "medicine", "mentorship", "museum", "networking", "pitch", "policy", "pre-law", "pre-med", "public health", "research", "robotics", "scholarship", "science", "seminar", "student", "technology", "training", "volunteer", "workshop", "youth"}
BEGINNER_WORDS = {"beginner", "all skill levels", "no experience", "new to", "first-time", "first time", "everyone welcome", "no coding required"}
TYPE_RULES = [("internship", "Internship"), ("apprenticeship", "Apprenticeship"), ("career fair", "Career fair"), ("law fair", "Law school fair"), ("hackathon", "Hackathon"), ("designathon", "Designathon"), ("workshop", "Workshop"), ("journal club", "Journal club"), ("seminar", "Seminar"), ("research", "Research"), ("fellowship", "Fellowship"), ("mentorship", "Mentorship"), ("volunteer", "Volunteer program"), ("pitch", "Pitch competition"), ("competition", "Competition"), ("conference", "Conference"), ("symposium", "Symposium"), ("training", "Training"), ("application", "Application")]
FIELD_RULES = [
    (("medicine", "medical", "health", "clinical", "hospital", "biomedical", "public health", "nursing", "pre-med"), "Medicine & Health"),
    (("law", "legal", "civic", "government", "policy", "public defense", "pre-law", "diplomacy"), "Law & Civic"),
    (("business", "entrepreneur", "startup", "finance", "marketing", "pitch", "founder"), "Business & Entrepreneurship"),
    (("engineering", "science", "climate", "robotics", "infrastructure", "stem", "energy"), "Engineering & Science"),
    (("art", "museum", "journalism", "media", "film", "music", "design", "creative"), "Arts & Media"),
    (("volunteer", "leadership", "service", "nonprofit", "youth council"), "Leadership & Service"),
    (("technology", "coding", "software", "cyber", "data", " ai ", "hackathon"), "Technology"),
]
_ROBOTS: dict[str, urllib.robotparser.RobotFileParser] = {}
_LAST_REQUEST: dict[str, float] = {}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def can_fetch(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root not in _ROBOTS:
        robots = urllib.robotparser.RobotFileParser(f"{root}/robots.txt")
        try:
            robots.read()
        except Exception:
            robots = urllib.robotparser.RobotFileParser()
            robots.set_url(f"{root}/robots.txt")
            robots.parse(["User-agent: *", "Disallow:"])
        _ROBOTS[root] = robots
    return _ROBOTS[root].can_fetch(USER_AGENT, url)


def fetch(url: str, timeout: int = 18) -> tuple[str, str]:
    if not can_fetch(url):
        raise PermissionError(f"robots.txt does not allow collection: {url}")
    host = urllib.parse.urlparse(url).netloc
    elapsed = time.monotonic() - _LAST_REQUEST.get(host, 0)
    if elapsed < 0.8:
        time.sleep(0.8 - elapsed)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/ld+json,application/json;q=0.9,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(3_000_000).decode(charset, errors="replace")
            return body, content_type
    finally:
        _LAST_REQUEST[host] = time.monotonic()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def iso_date(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", raw)
    if match:
        return match.group(0)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def iter_jsonld(document: Any) -> Iterable[dict[str, Any]]:
    if isinstance(document, list):
        for item in document:
            yield from iter_jsonld(item)
    elif isinstance(document, dict):
        if "@graph" in document:
            yield from iter_jsonld(document["@graph"])
        yield document


def extract_jsonld(page: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    pattern = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
    for raw in pattern.findall(page):
        try:
            parsed = json.loads(html.unescape(raw.strip()))
        except (json.JSONDecodeError, ValueError):
            continue
        for item in iter_jsonld(parsed):
            event_type = item.get("@type", "")
            types = event_type if isinstance(event_type, list) else [event_type]
            if any("Event" in str(value) for value in types):
                events.append(item)
    return events


def location_text(location: Any) -> str:
    if isinstance(location, str):
        return clean_text(location)
    if not isinstance(location, dict):
        return ""
    address = location.get("address")
    if isinstance(address, dict):
        parts = [location.get("name"), address.get("streetAddress"), address.get("addressLocality"), address.get("addressRegion")]
    else:
        parts = [location.get("name"), address]
    return ", ".join(clean_text(part) for part in parts if clean_text(part))


def city_from(text: str) -> str:
    for city in ("Bothell", "Seattle", "Bellevue", "Redmond", "Everett", "Tacoma", "Kirkland", "Renton", "Shoreline", "Lynnwood", "Woodinville"):
        if city.lower() in text.lower():
            return city
    return "Puget Sound"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70]
    return slug or hashlib.sha1(value.encode()).hexdigest()[:12]


def classify_type(text: str) -> str:
    lowered = f" {text.lower()} "
    for needle, label in TYPE_RULES:
        if needle in lowered:
            return label
    return "Workshop"


def classify_field(text: str) -> str:
    lowered = f" {text.lower()} "
    for needles, label in FIELD_RULES:
        if any(needle in lowered for needle in needles):
            return label
    return "Career & Research"


def schema_to_opportunity(item: dict[str, Any], source_url: str, trust: float, today: str | None = None) -> dict[str, Any] | None:
    title = clean_text(item.get("name"))
    start = iso_date(item.get("startDate"))
    if not title or not start:
        return None
    end = iso_date(item.get("endDate")) or start
    description = clean_text(item.get("description"))[:700]
    location = location_text(item.get("location"))
    combined = f" {title} {description} {location} "
    offers = item.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = offers.get("price") if isinstance(offers, dict) else None
    currency = offers.get("priceCurrency", "USD") if isinstance(offers, dict) else "USD"
    cost = "Free" if str(price).strip() in {"0", "0.0", "0.00"} or "free" in combined.lower() else (f"{price} {currency}" if price not in (None, "") else "See official page")
    organizer = item.get("organizer") or item.get("performer") or {}
    if isinstance(organizer, dict):
        organizer = organizer.get("name")
    organizer_name = clean_text(organizer) or urllib.parse.urlparse(source_url).netloc
    eligibility = "See the official page for eligibility"
    eligibility_patterns = [r"(?:open to|for) ([^.]{5,100})", r"(high school students[^.]{0,80})", r"(college students[^.]{0,80})", r"(all ages[^.]{0,80})"]
    for pattern in eligibility_patterns:
        match = re.search(pattern, description, re.I)
        if match:
            eligibility = clean_text(match.group(1)).strip(" ,;")
            break
    url = clean_text(item.get("url")) or (offers.get("url") if isinstance(offers, dict) else "") or source_url
    if url.startswith("/"):
        url = urllib.parse.urljoin(source_url, url)
    confidence = trust
    if any(word in combined.lower() for word in REGION_WORDS): confidence += 0.04
    if any(word in combined.lower() for word in OPPORTUNITY_WORDS): confidence += 0.04
    if description: confidence += 0.02
    confidence = round(min(confidence, 0.99), 2)
    beginner = any(word in combined.lower() for word in BEGINNER_WORDS)
    event_status = str(item.get("eventStatus", ""))
    status = "closed" if "Cancelled" in event_status else ("open" if isinstance(offers, dict) and offers.get("availability") else "announced")
    return {
        "id": f"{slugify(title)}-{start[:4]}", "title": title, "organizer": organizer_name,
        "field": classify_field(combined),
        "type": classify_type(combined), "format": "Online" if "online" in location.lower() else "In person",
        "city": city_from(location or combined), "venue": location or "See official page", "startDate": start,
        "endDate": end, "deadline": None, "status": status, "cost": cost, "eligibility": eligibility,
        "skillLevel": "Beginner" if beginner else "Not stated", "beginnerFriendly": beginner,
        "description": description or f"A newly announced {classify_type(combined).lower()} in the Puget Sound region.",
        "whyItStandsOut": "A recently announced local opportunity from a monitored source.",
        "sourceUrl": source_url, "registrationUrl": url, "verifiedAt": today or date.today().isoformat(),
        "tags": sorted({classify_type(combined).lower(), classify_field(combined).lower(), city_from(location or combined).lower()}), "confidence": confidence,
    }


def qualifies(item: dict[str, Any], today: date | None = None) -> tuple[bool, str]:
    current = today or date.today()
    end = iso_date(item.get("endDate")) or iso_date(item.get("startDate"))
    if not end or end < current.isoformat():
        return False, "expired or missing date"
    combined = " ".join(clean_text(item.get(key)) for key in ("title", "field", "type", "description", "venue", "city", "eligibility")) .lower()
    if not any(word in combined for word in REGION_WORDS) and item.get("format") != "Online":
        return False, "outside the coverage area"
    if not any(word in combined for word in OPPORTUNITY_WORDS):
        return False, "not a relevant student opportunity"
    if float(item.get("confidence", 0)) < 0.84:
        return False, "confidence below publish threshold"
    return True, "qualified"


def event_links(page: str, base_url: str, limit: int) -> list[str]:
    parser = LinkParser()
    parser.feed(page)
    base_host = urllib.parse.urlparse(base_url).netloc
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for href, label in parser.links:
        url = urllib.parse.urljoin(base_url, href).split("#")[0]
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base_host or url in seen:
            continue
        seen.add(url)
        text = f" {url.lower()} {label.lower()} "
        score = sum(2 for word in ("event", "intern", "career", "law", "health", "business", "engineering", "art", "leadership", "hack", "workshop", "student", "competition", "research") if word in text)
        if score:
            scored.append((score, url))
    return [url for _, url in sorted(scored, reverse=True)[:limit]]


def dedupe_key(item: dict[str, Any]) -> str:
    title = re.sub(r"\b20\d{2}\b", "", clean_text(item.get("title")).lower())
    title = re.sub(r"[^a-z0-9]+", "", title)
    return f"{title}:{item.get('startDate', '')}"
