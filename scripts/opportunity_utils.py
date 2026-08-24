#!/usr/bin/env python3
"""Shared, dependency-free utilities for the NextUp PNW data pipeline."""
from __future__ import annotations

import hashlib
import html
import json
import re
import threading
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
OPPORTUNITY_WORDS = {"application", "apprenticeship", "career", "case competition", "civic engagement", "coding", "community service", "competition", "conference", "designathon", "entrepreneurship", "fair", "fellowship", "hackathon", "information session", "info session", "internship", "journal club", "leadership program", "maker", "mentorship", "networking", "pitch", "pre-law", "pre-med", "research opportunity", "robotics", "scholarship", "seminar", "symposium", "training", "volunteer", "workshop", "youth council"}
BEGINNER_WORDS = {"beginner", "all skill levels", "no experience", "new to", "first-time", "first time", "everyone welcome", "no coding required"}
CALENDAR_NOISE_PATTERNS = (
    r"\bdaily \d+ minute movement break\b",
    r"\bweight training class\b",
    r"\s+vs\.?\s+",
    r"\bcurriculum (?:day|meeting)\b",
    r"\b(?:committee|council|department) meeting\b",
    r"\bnew faculty\b",
    r"\binternal funding\b",
    r"\bteaching with (?:canvas|digital tools)\b",
    r"\bcanvas features that support grading\b",
    r"\bmfa show\b",
    r"\b(?:bingo|trivia)\b",
    r"\bretir(?:e|ement|ing)\b",
    r"\bconvocation\b",
    r"\b(?:quarter break|labor day|memorial day|holiday)\b",
    r"\bsurplus (?:public|online) store\b",
)
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
_HOST_LOCKS: dict[str, threading.Lock] = {}
_HOST_LOCKS_GUARD = threading.Lock()


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
        robots_url = f"{root}/robots.txt"
        robots = urllib.robotparser.RobotFileParser(robots_url)
        try:
            request = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=5) as response:
                content = response.read(512_000).decode("utf-8", errors="replace")
            robots.parse(content.splitlines())
        except Exception:
            robots = urllib.robotparser.RobotFileParser()
            robots.set_url(robots_url)
            robots.parse(["User-agent: *", "Disallow:"])
        _ROBOTS[root] = robots
    return _ROBOTS[root].can_fetch(USER_AGENT, url)


def fetch(url: str, timeout: int = 18) -> tuple[str, str]:
    host = urllib.parse.urlparse(url).netloc
    with _HOST_LOCKS_GUARD:
        host_lock = _HOST_LOCKS.setdefault(host, threading.Lock())
    with host_lock:
        if not can_fetch(url):
            raise PermissionError(f"robots.txt does not allow collection: {url}")
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


def canonical_url(value: Any) -> str:
    """Return a stable public URL without fragments or tracking parameters."""
    raw = clean_text(value)
    if not raw:
        return ""
    parsed = urllib.parse.urlsplit(raw)
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = sorted((key, val) for key, val in query if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"})
    return urllib.parse.urlunsplit(((parsed.scheme or "https").lower(), hostname + port, path, urllib.parse.urlencode(query), ""))


def iso_date(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", raw)
    if match:
        candidate = match.group(0)
        try:
            return datetime.strptime(candidate, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None
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


def unique_opportunity_id(item: dict[str, Any], used_ids: set[str]) -> str:
    """Return a stable, URL-safe ID that does not collide with existing pages."""
    preferred = clean_text(item.get("id")) or f"{slugify(clean_text(item.get('title')))}-{str(item.get('startDate', ''))[:4]}"
    if preferred not in used_ids:
        return preferred

    start = str(item.get("startDate", "")).replace("-", "")
    dated = f"{preferred}-{start[4:]}" if len(start) == 8 else preferred
    if dated not in used_ids:
        return dated

    fingerprint = hashlib.sha1(
        f"{dedupe_key(item)}:{item.get('sourceUrl', '')}:{item.get('registrationUrl', '')}".encode()
    ).hexdigest()[:8]
    candidate = f"{dated}-{fingerprint}"
    counter = 2
    while candidate in used_ids:
        candidate = f"{dated}-{fingerprint}-{counter}"
        counter += 1
    return candidate


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
    raw_url = clean_text(item.get("url")) or clean_text(offers.get("url") if isinstance(offers, dict) else "")
    url = urllib.parse.urljoin(source_url, raw_url) if raw_url else ""
    confidence = trust
    if any(word in combined.lower() for word in REGION_WORDS): confidence += 0.04
    if any(word in combined.lower() for word in OPPORTUNITY_WORDS): confidence += 0.04
    if description: confidence += 0.02
    confidence = round(min(confidence, 0.99), 2)
    beginner = any(word in combined.lower() for word in BEGINNER_WORDS)
    event_status = str(item.get("eventStatus", "")).lower()
    status = "closed" if "cancel" in event_status else ("open" if isinstance(offers, dict) and offers.get("availability") else "announced")
    return {
        "id": f"{slugify(title)}-{start[:4]}", "title": title, "organizer": organizer_name,
        "field": classify_field(combined),
        "type": classify_type(combined), "format": "Online" if "online" in location.lower() else "In person",
        "city": city_from(location or combined), "venue": location or "See official page", "startDate": start,
        "endDate": end, "deadline": None, "status": status, "cost": cost, "eligibility": eligibility,
        "skillLevel": "Beginner" if beginner else "Not stated", "beginnerFriendly": beginner,
        "description": description or f"A newly announced {classify_type(combined).lower()} in the Puget Sound region.",
        "_descriptionGenerated": not bool(description),
        "_eventUrlPresent": bool(raw_url),
        "whyItStandsOut": "A recently announced local opportunity from a monitored source.",
        "sourceUrl": source_url, "registrationUrl": url, "verifiedAt": today or date.today().isoformat(),
        "tags": sorted({classify_type(combined).lower(), classify_field(combined).lower(), city_from(location or combined).lower()}), "confidence": confidence,
    }


def qualifies(item: dict[str, Any], today: date | None = None) -> tuple[bool, str]:
    current = today or date.today()
    end = iso_date(item.get("endDate")) or iso_date(item.get("startDate"))
    if not end or end < current.isoformat():
        return False, "expired or missing date"
    if clean_text(item.get("status")).lower() == "closed":
        return False, "cancelled or closed"
    detail_url = clean_text(item.get("registrationUrl"))
    if "_eventUrlPresent" not in item:
        detail_url = detail_url or clean_text(item.get("sourceUrl"))
    parsed_url = urllib.parse.urlparse(detail_url)
    if item.get("_eventUrlPresent") is False or parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        return False, "missing official detail URL"
    combined = " ".join(clean_text(item.get(key)) for key in ("title", "organizer", "field", "type", "description", "venue", "city", "eligibility", "sourceUrl")) .lower()
    region_fields = ("title", "organizer", "description", "venue", "eligibility", "sourceUrl")
    region_text = " ".join(clean_text(item.get(key)) for key in region_fields).lower()
    city = clean_text(item.get("city"))
    if city and city != "Puget Sound":
        region_text += " " + city.lower()
    if not any(word in region_text for word in REGION_WORDS):
        return False, "outside the coverage area"
    relevance_fields = ["title", "eligibility", "whyItStandsOut"]
    generated_description = bool(item.get("_descriptionGenerated")) or clean_text(item.get("description")).lower().startswith("a newly announced ")
    if not generated_description:
        relevance_fields.append("description")
    relevance_text = " ".join(clean_text(item.get(key)) for key in relevance_fields).lower()
    title = clean_text(item.get("title")).lower()
    if any(re.search(pattern, title) for pattern in CALENDAR_NOISE_PATTERNS):
        return False, "not a relevant student opportunity"
    if re.search(r"\b(?:events|calendar)$", title) and not any(word in title for word in OPPORTUNITY_WORDS):
        return False, "not a relevant student opportunity"
    if not any(word in relevance_text for word in OPPORTUNITY_WORDS):
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
    organizer = re.sub(r"[^a-z0-9]+", "", clean_text(item.get("organizer")).lower())
    event_url = canonical_url(item.get("registrationUrl") or item.get("sourceUrl"))
    return f"{title}:{item.get('startDate', '')}:{organizer}:{event_url}"
