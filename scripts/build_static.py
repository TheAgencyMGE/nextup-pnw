#!/usr/bin/env python3
"""Build the zero-backend GitHub Pages site from the canonical JSON data."""
from __future__ import annotations

import html
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from opportunity_utils import DATA_FILE, ROOT, load_json

OUT = ROOT / "docs"
ASSETS = OUT / "assets"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def date_label(start: str, end: str | None) -> str:
    first = datetime.strptime(start, "%Y-%m-%d")
    if not end or end == start:
        return f"{first.strftime('%b')} {first.day}, {first.year}"
    last = datetime.strptime(end, "%Y-%m-%d")
    if first.month == last.month:
        return f"{first.strftime('%b')} {first.day}–{last.day}, {last.year}"
    return f"{first.strftime('%b')} {first.day}–{last.strftime('%b')} {last.day}, {last.year}"


def replace(template: str, values: dict[str, object]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def card(item: dict) -> str:
    searchable = " ".join([item["title"], item["organizer"], item["field"], item["city"], item["type"], item["description"], *item.get("tags", [])]).lower()
    tags = [item["field"], item["city"], item["type"], item["cost"]]
    if item.get("beginnerFriendly"):
        tags.append("Beginner-friendly")
    tag_html = "".join(f'<span class="{"beginner" if tag == "Beginner-friendly" else ""}">{esc(tag)}</span>' for tag in tags)
    deadline_html = f'<div class="deadline"><span class="footer-label">Deadline</span><p>{esc(date_label(item["deadline"], item["deadline"]))}</p></div>' if item.get("deadline") else ""
    short_date = re.sub(r", 20\d{2}", "", date_label(item["startDate"], item.get("endDate")))
    return f'''<article class="opportunity-card" data-city="{esc(item['city'])}" data-field="{esc(item['field'])}" data-beginner="{str(bool(item.get('beginnerFriendly'))).lower()}" data-search="{esc(searchable)}">
      <div class="card-topline"><span class="status status-{esc(item['status'])}">{esc(item['status'])}</span><span class="verified" title="Last checked {esc(item['verifiedAt'])}"><span>✓</span> Verified</span></div>
      <div class="date-block"><strong>{esc(short_date)}</strong><span>{esc(item['startDate'][:4])}</span></div>
      <h3>{esc(item['title'])}</h3><p class="organizer">{esc(item['organizer'])}</p><p class="card-description">{esc(item['description'])}</p>
      <div class="tag-row">{tag_html}</div><div class="standout"><span>↗</span><p><strong>Why it stands out</strong>{esc(item['whyItStandsOut'])}</p></div>
      <div class="card-footer"><div><span class="footer-label">Eligibility</span><p>{esc(item['eligibility'])}</p></div>{deadline_html}</div>
      <a class="primary-link" href="opportunities/{esc(item['id'])}/">View details <span>↗</span></a></article>'''


def build_detail(item: dict, base_url: str, submit_url: str) -> str:
    template = (ROOT / "static" / "detail.template.html").read_text(encoding="utf-8")
    canonical = f"{base_url}/opportunities/{item['id']}/"
    event = {"@context":"https://schema.org","@type":"Event","name":item["title"],"description":item["description"],"startDate":item["startDate"],"endDate":item.get("endDate") or item["startDate"],"eventAttendanceMode":"https://schema.org/OnlineEventAttendanceMode" if item["format"] == "Online" else "https://schema.org/OfflineEventAttendanceMode","eventStatus":"https://schema.org/EventScheduled","location":{"@type":"Place","name":item["venue"],"address":{"@type":"PostalAddress","addressLocality":item["city"],"addressRegion":"WA","addressCountry":"US"}},"organizer":{"@type":"Organization","name":item["organizer"],"url":item["sourceUrl"]},"url":item.get("registrationUrl") or item["sourceUrl"]}
    return replace(template, {"TITLE":esc(item["title"]),"DESCRIPTION":esc(item["description"]),"CANONICAL":canonical,"JSON_LD":json.dumps(event).replace("</", "<\\/"),"SUBMIT_URL":submit_url,"STATUS":esc(item["status"]),"VERIFIED":esc(item["verifiedAt"]),"FIELD":esc(item["field"]),"TYPE":esc(item["type"]),"CITY":esc(item["city"]),"WHY":esc(item["whyItStandsOut"]),"OFFICIAL_URL":esc(item.get("registrationUrl") or item["sourceUrl"]),"DATE":esc(date_label(item["startDate"],item.get("endDate"))),"VENUE":esc(item["venue"]),"ELIGIBILITY":esc(item["eligibility"]),"COST":esc(item["cost"]),"FORMAT":esc(item["format"])})


def main() -> int:
    repository = os.getenv("GITHUB_REPOSITORY", "TheAgencyMGE/nextup-pnw")
    owner, repo = repository.split("/", 1)
    base_url = (os.getenv("SITE_URL") or f"https://{owner.lower()}.github.io/{repo}").rstrip("/")
    repo_url = f"https://github.com/{repository}"
    submit_url = f"{repo_url}/issues/new?template=submit-opportunity.yml"
    items = sorted((item for item in load_json(DATA_FILE, []) if item.get("status") != "closed"), key=lambda item: item["startDate"])
    opportunity_pages = OUT / "opportunities"
    if opportunity_pages.exists():
        shutil.rmtree(opportunity_pages)
    OUT.mkdir(exist_ok=True); ASSETS.mkdir(exist_ok=True)
    css = (ROOT / "app" / "globals.css").read_text(encoding="utf-8")
    css = re.sub(r'^@import[^\n]+\n+', '', css)
    (ASSETS / "styles.css").write_text(css, encoding="utf-8")
    shutil.copy2(ROOT / "static" / "app.js", ASSETS / "app.js")
    shutil.copy2(ROOT / "public" / "favicon.svg", ASSETS / "favicon.svg")
    shutil.copy2(ROOT / "public" / "og.png", ASSETS / "og.png")
    next_item = items[0]
    next_date = datetime.strptime(next_item["startDate"], "%Y-%m-%d")
    template = (ROOT / "static" / "index.template.html").read_text(encoding="utf-8")
    index = replace(template, {"BASE_URL":base_url,"SUBMIT_URL":submit_url,"REPO_URL":repo_url,"NEXT_DAY":next_date.day,"NEXT_MONTH":next_date.strftime("%b").upper(),"NEXT_YEAR":next_date.year,"NEXT_TITLE":esc(next_item["title"]),"NEXT_TYPE":esc(next_item["field"]),"NEXT_CITY":esc(next_item["city"]),"CITY_OPTIONS":"".join(f"<option>{esc(value)}</option>" for value in sorted({item['city'] for item in items})),"FIELD_OPTIONS":"".join(f"<option>{esc(value)}</option>" for value in sorted({item['field'] for item in items})),"COUNT":len(items),"CARDS":"".join(card(item) for item in items)})
    (OUT / "index.html").write_text(index, encoding="utf-8")
    for item in items:
        directory = OUT / "opportunities" / item["id"]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "index.html").write_text(build_detail(item, base_url, submit_url), encoding="utf-8")
    sitemap_urls = [f"{base_url}/", *(f"{base_url}/opportunities/{item['id']}/" for item in items)]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{html.escape(url)}</loc></url>' for url in sitemap_urls) + '</urlset>', encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8")
    (OUT / "manifest.webmanifest").write_text(json.dumps({"name":"NextUp PNW","short_name":"NextUp","start_url":"./","display":"standalone","background_color":"#f4f0e5","theme_color":"#173f31","icons":[]}), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    host = base_url.removeprefix("https://").removeprefix("http://").split("/", 1)[0]
    cname = OUT / "CNAME"
    if host and not host.endswith("github.io"):
        cname.write_text(host + "\n", encoding="utf-8")
    elif cname.exists():
        cname.unlink()
    (OUT / "404.html").write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Not found — NextUp PNW</title><style>body{font:18px system-ui;background:#f4f0e5;color:#10251e;display:grid;place-items:center;min-height:90vh;text-align:center}a{color:#173f31;font-weight:800}</style><main><h1>That opportunity moved on.</h1><p><a href="./">See what\'s next →</a></p></main>', encoding="utf-8")
    print(f"Built {len(items)} opportunities for {base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
