#!/usr/bin/env python3
"""Dependency-free adapters that turn public calendars into event-shaped records."""
from __future__ import annotations

import copy
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any, Iterable

from opportunity_utils import clean_text, extract_jsonld


class AdapterError(ValueError):
    """A feed declared a format that could not be decoded by its adapter."""


def _event_instances(event: dict[str, Any]) -> Iterable[dict[str, Any]]:
    instances = event.get("event_instances") or event.get("instances") or []
    if not instances:
        yield event
        return
    for wrapped in instances:
        instance = wrapped.get("event_instance", wrapped) if isinstance(wrapped, dict) else {}
        record = copy.deepcopy(event)
        record["startDate"] = instance.get("start") or instance.get("startDate")
        record["endDate"] = instance.get("end") or instance.get("endDate") or record["startDate"]
        yield record


def _json_record(value: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    event = value.get("event", value)
    if not isinstance(event, dict):
        return []
    output: list[dict[str, Any]] = []
    for instance in _event_instances(event):
        name = instance.get("name") or instance.get("title") or instance.get("summary")
        start = instance.get("startDate") or instance.get("start") or instance.get("starts_at") or instance.get("startDateTime")
        if not name or not start:
            continue
        geo = instance.get("geo") if isinstance(instance.get("geo"), dict) else {}
        city = geo.get("city") or instance.get("city")
        state = geo.get("state") or instance.get("state")
        location_name = instance.get("location_name") or instance.get("venue_name") or instance.get("location")
        if str(instance.get("locationType", "")).lower() in {"online", "virtual"}:
            location_name = "Online"
        if location_name == "Online":
            location = "Online"
        elif isinstance(location_name, dict):
            location: Any = location_name
        else:
            location = {
                "@type": "Place",
                "name": clean_text(location_name),
                "address": {"addressLocality": clean_text(city), "addressRegion": clean_text(state)},
            }
        web_link = clean_text(instance.get("webLink"))
        web_link_match = re.search(r'href=["\']([^"\']+)', html.unescape(web_link), re.I)
        url = instance.get("url") or instance.get("localist_url") or instance.get("permaLinkUrl") or instance.get("link") or (web_link_match.group(1) if web_link_match else "")
        output.append({
            "@type": "Event",
            "name": clean_text(name),
            "description": clean_text(instance.get("description") or instance.get("description_text") or instance.get("content")),
            "startDate": start,
            "endDate": instance.get("endDate") or instance.get("end") or instance.get("ends_at") or instance.get("endDateTime") or start,
            "location": location,
            "url": urllib.parse.urljoin(source_url, clean_text(url)) if url else "",
            "organizer": instance.get("organizer") or instance.get("department") or {},
            "offers": instance.get("offers") or {},
            "eventStatus": "Cancelled" if instance.get("canceled") else (instance.get("eventStatus") or instance.get("status") or ""),
        })
    return output


def _extract_json(body: str, source_url: str) -> list[dict[str, Any]]:
    try:
        document = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AdapterError(f"malformed JSON: {exc}") from exc
    if isinstance(document, list):
        values = document
    elif isinstance(document, dict):
        values = document.get("events") or document.get("results") or document.get("items") or document.get("data") or [document]
    else:
        return []
    if isinstance(values, dict):
        values = values.get("events") or values.get("items") or list(values.values())
    output: list[dict[str, Any]] = []
    for value in values if isinstance(values, list) else []:
        if isinstance(value, dict):
            output.extend(_json_record(value, source_url))
    return output


def _extract_tribe(body: str, source_url: str) -> list[dict[str, Any]]:
    """Extract The Events Calendar (WordPress Tribe REST API) records."""
    try:
        document = json.loads(body)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AdapterError(f"malformed JSON: {exc}") from exc
    values = document.get("events", []) if isinstance(document, dict) else []
    output: list[dict[str, Any]] = []
    for event in values if isinstance(values, list) else []:
        if not isinstance(event, dict):
            continue
        name = clean_text(event.get("title"))
        start = event.get("start_date") or event.get("startDate")
        if not name or not start:
            continue
        venue = event.get("venue") if isinstance(event.get("venue"), dict) else {}
        organizers = event.get("organizer") if isinstance(event.get("organizer"), list) else []
        organizer_name = clean_text(organizers[0].get("organizer")) if organizers and isinstance(organizers[0], dict) else ""
        cost = clean_text(event.get("cost"))
        offers: dict[str, Any] = {}
        if cost.lower() == "free":
            offers = {"price": "0", "priceCurrency": "CAD"}
        elif cost:
            offers = {"price": cost, "priceCurrency": "CAD"}
        output.append({
            "@type": "Event",
            "name": name,
            "description": clean_text(event.get("description") or event.get("excerpt")),
            "startDate": start,
            "endDate": event.get("end_date") or event.get("endDate") or start,
            "location": {
                "@type": "Place",
                "name": clean_text(venue.get("venue")),
                "address": {
                    "streetAddress": clean_text(venue.get("address")),
                    "addressLocality": clean_text(venue.get("city")),
                    "addressRegion": clean_text(venue.get("province") or venue.get("stateprovince") or venue.get("state")),
                },
            },
            "url": urllib.parse.urljoin(source_url, clean_text(event.get("url"))),
            "organizer": {"name": organizer_name} if organizer_name else {},
            "offers": offers,
            "eventStatus": event.get("status", ""),
        })
    return output


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for child in node.iter():
        if child is not node and _local_name(child.tag) in wanted and child.text:
            return clean_text(child.text)
    return ""


def _extract_xml(body: str, source_url: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise AdapterError(f"malformed XML: {exc}") from exc
    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    output: list[dict[str, Any]] = []
    for entry in entries:
        link = _child_text(entry, "link", "url")
        if not link:
            for child in entry.iter():
                if _local_name(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        name = _child_text(entry, "title", "name")
        start = _child_text(entry, "startdate", "start", "dtstart", "eventstart")
        if not name or not start:
            continue
        output.append({
            "@type": "Event",
            "name": name,
            "description": _child_text(entry, "description", "summary", "content"),
            "startDate": start,
            "endDate": _child_text(entry, "enddate", "end", "dtend", "eventend") or start,
            "location": _child_text(entry, "location", "venue"),
            "url": urllib.parse.urljoin(source_url, link) if link else "",
            "organizer": _child_text(entry, "organizer", "author"),
        })
    return output


def _ical_value(value: str) -> str:
    return value.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _ical_date(value: str) -> str:
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", value)
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else value


def _extract_ical(body: str, source_url: str) -> list[dict[str, Any]]:
    upper_body = body.upper()
    if "BEGIN:VCALENDAR" not in upper_body or "END:VCALENDAR" not in upper_body:
        raise AdapterError("malformed iCalendar: missing VCALENDAR envelope")
    if upper_body.count("BEGIN:VEVENT") != upper_body.count("END:VEVENT"):
        raise AdapterError("malformed iCalendar: unbalanced VEVENT")
    unfolded = re.sub(r"\r?\n[ \t]", "", body)
    events = re.findall(r"BEGIN:VEVENT\r?\n(.*?)\r?\nEND:VEVENT", unfolded, re.I | re.S)
    output: list[dict[str, Any]] = []
    for event in events:
        fields: dict[str, str] = {}
        for line in event.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.split(";", 1)[0].upper()] = _ical_value(value.strip())
        if not fields.get("SUMMARY") or not fields.get("DTSTART"):
            continue
        start = _ical_date(fields["DTSTART"])
        output.append({
            "@type": "Event",
            "name": clean_text(fields["SUMMARY"]),
            "description": clean_text(fields.get("DESCRIPTION")),
            "startDate": start,
            "endDate": _ical_date(fields.get("DTEND", fields["DTSTART"])),
            "location": clean_text(fields.get("LOCATION")),
            "url": urllib.parse.urljoin(source_url, fields["URL"]) if fields.get("URL") else "",
            "organizer": clean_text(re.sub(r"^mailto:", "", fields.get("ORGANIZER", ""), flags=re.I)),
            "eventStatus": fields.get("STATUS", ""),
        })
    return output


class _CardParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.records: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.depth = 0
        self.capture: list[tuple[str, int]] = []
        self.buffers: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").lower()
        if self.current is None and tag in {"article", "li", "div"} and any(word in classes for word in ("event", "calendar-item", "result-card")):
            self.current = {}
            self.depth = 1
        elif self.current is not None:
            self.depth += 1
        if self.current is None:
            return
        if tag == "a" and values.get("href"):
            self.current.setdefault("url", urllib.parse.urljoin(self.base_url, values["href"]))
            self.capture.append(("name", self.depth))
            self.buffers.setdefault("name", [])
        if tag == "time" and values.get("datetime"):
            self.current.setdefault("startDate", values["datetime"])
        if any(word in classes for word in ("description", "summary", "excerpt")):
            self.capture.append(("description", self.depth))
            self.buffers.setdefault("description", [])
        if any(word in classes for word in ("location", "venue")):
            self.capture.append(("location", self.depth))
            self.buffers.setdefault("location", [])

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            for key, _ in self.capture:
                self.buffers.setdefault(key, []).append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        for key, level in list(self.capture):
            if level == self.depth:
                value = clean_text(" ".join(self.buffers.get(key, [])))
                if value:
                    self.current.setdefault(key, value)
                self.capture.remove((key, level))
        self.depth -= 1
        if self.depth == 0:
            if self.current.get("name") and self.current.get("startDate") and self.current.get("url"):
                self.current.setdefault("endDate", self.current["startDate"])
                self.current["@type"] = "Event"
                self.records.append(self.current)
            self.current = None
            self.buffers = {}
            self.capture = []


def _extract_html_cards(body: str, source_url: str) -> list[dict[str, Any]]:
    parser = _CardParser(source_url)
    parser.feed(body)
    return parser.records


def extract_records(body: str, content_type: str, source_url: str, adapter: str = "auto") -> list[dict[str, Any]]:
    """Extract event-shaped dictionaries from a supported public feed or page."""
    selected = (adapter or "auto").lower()
    mime = (content_type or "").split(";", 1)[0].lower()
    stripped = body.lstrip()
    if selected == "tribe":
        return _extract_tribe(body, source_url)
    if selected in {"json", "localist", "trumba"} or (selected == "auto" and ("json" in mime or stripped.startswith(("{", "[")))):
        return _extract_json(body, source_url)
    if selected in {"rss", "atom", "xml"} or (selected == "auto" and ("xml" in mime or stripped.startswith("<?xml"))):
        return _extract_xml(body, source_url)
    if selected in {"ics", "ical", "icalendar"} or (selected == "auto" and ("calendar" in mime or "BEGIN:VCALENDAR" in body[:200])):
        return _extract_ical(body, source_url)
    if selected in {"jsonld", "html", "auto"}:
        structured = extract_jsonld(body)
        return structured or _extract_html_cards(body, source_url)
    raise AdapterError(f"unsupported adapter: {selected}")
