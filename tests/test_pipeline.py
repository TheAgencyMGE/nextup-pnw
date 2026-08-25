import json
import os
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_static import date_label
from opportunity_utils import _ROBOTS, can_fetch, canonical_url, dedupe_key, extract_jsonld, qualifies, schema_to_opportunity, unique_opportunity_id


class PipelineTests(unittest.TestCase):
    def test_robots_fetch_is_bounded_and_honors_disallow(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, *_):
                return b"User-agent: *\nDisallow: /private\n"

        def urlopen(_request, timeout):
            self.assertEqual(timeout, 5)
            return Response()

        _ROBOTS.clear()
        with patch("opportunity_utils.urllib.request.urlopen", side_effect=urlopen):
            self.assertFalse(can_fetch("https://example.org/private/event"))

    def test_date_label_is_portable(self):
        self.assertEqual(date_label("2099-01-03", None), "Jan 3, 2099")

    def test_extracts_and_qualifies_local_schema_event(self):
        page = '''<script type="application/ld+json">{"@context":"https://schema.org","@type":"Event","name":"Seattle Student Coding Workshop","startDate":"2099-10-03","endDate":"2099-10-03","description":"Free beginner workshop open to high school students in Seattle.","location":{"@type":"Place","name":"Seattle Central Library","address":{"addressLocality":"Seattle","addressRegion":"WA"}},"offers":{"price":"0","url":"https://example.org/register"}}</script>'''
        events = extract_jsonld(page)
        self.assertEqual(len(events), 1)
        item = schema_to_opportunity(events[0], "https://example.org/event", 0.9, "2099-01-01")
        self.assertIsNotNone(item)
        allowed, reason = qualifies(item, date(2099, 1, 1))
        self.assertTrue(allowed, reason)
        self.assertEqual(item["cost"], "Free")
        self.assertTrue(item["beginnerFriendly"])

    def test_rejects_expired_event(self):
        item = {"title":"Seattle Hackathon","description":"student coding","venue":"Seattle","city":"Seattle","eligibility":"students","startDate":"2020-01-01","endDate":"2020-01-02","format":"In person","confidence":0.99}
        self.assertFalse(qualifies(item, date(2026, 1, 1))[0])

    def test_rejects_online_event_without_pnw_connection(self):
        item = {
            "title": "Online Student Coding Workshop",
            "organizer": "Example Learning Company",
            "description": "A beginner workshop for students everywhere.",
            "venue": "Online",
            "city": "Online",
            "eligibility": "Students",
            "startDate": "2099-01-03",
            "endDate": "2099-01-03",
            "format": "Online",
            "confidence": 0.99,
            "sourceUrl": "https://example.org/workshop",
        }
        self.assertEqual(qualifies(item, date(2099, 1, 1)), (False, "outside the coverage area"))

    def test_accepts_online_event_with_pnw_organizer(self):
        item = {
            "title": "Online Student Coding Workshop",
            "organizer": "Seattle Public Library",
            "description": "A beginner workshop for students.",
            "venue": "Online",
            "city": "Puget Sound",
            "eligibility": "Students",
            "startDate": "2099-01-03",
            "endDate": "2099-01-03",
            "format": "Online",
            "confidence": 0.99,
            "sourceUrl": "https://spl.org/events/workshop",
        }
        self.assertTrue(qualifies(item, date(2099, 1, 1))[0])

    def test_rejects_calendar_noise_despite_generated_workshop_type(self):
        base = {
            "organizer": "University of Washington",
            "description": "An official UW Seattle campus calendar entry.",
            "venue": "Seattle Campus",
            "city": "Seattle",
            "eligibility": "See official page",
            "startDate": "2099-09-01",
            "endDate": "2099-09-01",
            "format": "In person",
            "confidence": 0.99,
            "sourceUrl": "https://washington.edu/calendar",
            "type": "Workshop",
            "field": "Career & Research",
        }
        for title in ("Labor Day", "Quarter Break - Autumn 2099", "UW Surplus Public Store", "Daily 15 Minute Movement Break", "Virtual Weight Training Class"):
            with self.subTest(title=title):
                self.assertEqual(qualifies(base | {"title": title}, date(2099, 1, 1)), (False, "not a relevant student opportunity"))

    def test_rejects_passive_sports_and_internal_meetings_despite_keywords(self):
        base = {
            "organizer": "Seattle University",
            "description": "Student training, career development, and competition on a Seattle campus.",
            "venue": "Seattle Campus",
            "city": "Seattle",
            "eligibility": "Students",
            "startDate": "2099-09-01",
            "endDate": "2099-09-01",
            "format": "In person",
            "confidence": 0.99,
            "sourceUrl": "https://seattleu.edu/calendar",
        }
        for title in ("Women's Soccer vs. Nevada", "CSS Curriculum Meeting", "Mechanical Engineering Committee Meeting", "New Faculty Onboarding", "New Faculty – Introduction to Canvas", "Internal Funding and RRF Workshop", "Teaching with Canvas: A Refresher Workshop", "2026 Fall MFA Show", "Retro-Rewind Drag Bingo & Trivia", "PERS Retirement Workshop", "Convocation Address and Playfair"):
            with self.subTest(title=title):
                self.assertEqual(qualifies(base | {"title": title}, date(2099, 1, 1)), (False, "not a relevant student opportunity"))

    def test_generated_fallback_description_is_not_relevance_evidence(self):
        schema = {
            "@type": "Event", "name": "Seattle Community Gathering", "startDate": "2099-09-01",
            "location": {"name": "Seattle Center", "address": {"addressLocality": "Seattle", "addressRegion": "WA"}},
            "url": "https://example.org/events/gathering",
        }
        item = schema_to_opportunity(schema, "https://example.org/events", 0.97, "2099-01-01")
        self.assertIsNotNone(item)
        self.assertEqual(qualifies(item, date(2099, 1, 1)), (False, "not a relevant student opportunity"))

    def test_rejects_missing_or_invalid_detail_url(self):
        base = {
            "@type": "Event", "name": "Seattle Student Coding Workshop", "startDate": "2099-09-01",
            "description": "A coding workshop for students in Seattle.", "location": "Seattle",
        }
        for url in (None, "javascript:alert(1)"):
            with self.subTest(url=url):
                schema = base | ({"url": url} if url is not None else {})
                item = schema_to_opportunity(schema, "https://example.org/events", 0.97, "2099-01-01")
                self.assertIsNotNone(item)
                self.assertEqual(qualifies(item, date(2099, 1, 1)), (False, "missing official detail URL"))

    def test_resolves_relative_detail_url(self):
        schema = {
            "@type": "Event", "name": "Seattle Student Coding Workshop", "startDate": "2099-09-01",
            "description": "A coding workshop for students in Seattle.", "location": "Seattle", "url": "event/123",
        }
        item = schema_to_opportunity(schema, "https://example.org/calendar/", 0.97, "2099-01-01")
        self.assertEqual(item["registrationUrl"], "https://example.org/calendar/event/123")

    def test_rejects_invalid_calendar_date_without_builder_crash(self):
        schema = {"@type": "Event", "name": "Seattle Coding Workshop", "startDate": "2099-99-99", "url": "https://example.org/event"}
        self.assertIsNone(schema_to_opportunity(schema, "https://example.org/events", 0.97, "2099-01-01"))

    def test_rejects_cancelled_status_case_insensitively(self):
        schema = {
            "@type": "Event", "name": "Seattle Coding Workshop", "startDate": "2099-09-01",
            "description": "A coding workshop for Seattle students.", "location": "Seattle",
            "url": "https://example.org/event", "eventStatus": "CANCELLED",
        }
        item = schema_to_opportunity(schema, "https://example.org/events", 0.97, "2099-01-01")
        self.assertEqual(qualifies(item, date(2099, 1, 1)), (False, "cancelled or closed"))

    def test_rejects_generic_calendar_landing_record_despite_description_keywords(self):
        item = {
            "title": "signature tech events",
            "organizer": "GeekWire Events Calendar",
            "description": "Find conferences, networking, workshops, and technology events in Seattle.",
            "venue": "Seattle",
            "city": "Seattle",
            "eligibility": "See official page",
            "startDate": "2099-09-01",
            "endDate": "2099-09-01",
            "format": "In person",
            "confidence": 0.99,
            "sourceUrl": "https://geekwire.com/calendar",
        }
        self.assertEqual(qualifies(item, date(2099, 1, 1)), (False, "not a relevant student opportunity"))

    def test_accepts_explicit_skill_building_and_career_events(self):
        base = {
            "organizer": "University of Washington",
            "description": "Open to learners in Seattle.",
            "venue": "Seattle Campus",
            "city": "Seattle",
            "eligibility": "Students and community members",
            "startDate": "2099-09-01",
            "endDate": "2099-09-01",
            "format": "In person",
            "confidence": 0.99,
            "sourceUrl": "https://washington.edu/calendar",
            "type": "Workshop",
            "field": "Career & Research",
        }
        for title in ("Data Visualization Workshop", "Public Health Research Seminar", "Graduate Certificate Information Session", "Engineering Internship Fair"):
            with self.subTest(title=title):
                self.assertTrue(qualifies(base | {"title": title}, date(2099, 1, 1))[0])

    def test_dedupe_normalizes_year(self):
        left = {"title":"Example Hackathon 2026","organizer":"Seattle Tech","startDate":"2026-10-01"}
        right = {"title":"Example Hackathon","organizer":"Seattle Tech","startDate":"2026-10-01"}
        self.assertEqual(dedupe_key(left), dedupe_key(right))

    def test_dedupe_does_not_merge_different_organizers(self):
        left = {"title":"Student Workshop","organizer":"Seattle Library","startDate":"2099-10-01"}
        right = {"title":"Student Workshop","organizer":"Tacoma Library","startDate":"2099-10-01"}
        self.assertNotEqual(dedupe_key(left), dedupe_key(right))

    def test_canonical_url_removes_tracking_and_normalizes_host(self):
        left = "https://WWW.Example.org/events/workshop/?utm_source=newsletter&b=2&a=1#details"
        right = "https://example.org/events/workshop?a=1&b=2"
        self.assertEqual(canonical_url(left), right)

    def test_recurring_events_receive_unique_page_ids(self):
        used = {"student-workshop-2026"}
        item = {
            "id": "student-workshop-2026",
            "title": "Student Workshop",
            "startDate": "2026-10-24",
            "sourceUrl": "https://example.org/workshop",
        }
        generated = unique_opportunity_id(item, used)
        self.assertEqual(generated, "student-workshop-2026-1024")
        self.assertNotIn(generated, used)

    def test_seed_data_has_required_fields_and_unique_ids(self):
        data = json.loads((ROOT / "data" / "opportunities.json").read_text(encoding="utf-8"))
        required = {"id","title","organizer","field","type","city","startDate","status","eligibility","sourceUrl","verifiedAt"}
        self.assertGreaterEqual(len(data), 35)
        self.assertGreaterEqual(len({item["field"] for item in data}), 8)
        self.assertEqual(len({item["id"] for item in data}), len(data))
        for item in data:
            self.assertFalse(required - item.keys())

    def test_source_catalog_uses_unique_official_https_endpoints(self):
        sources = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(sources), 43)
        self.assertEqual(len({source["id"] for source in sources}), len(sources))
        self.assertGreaterEqual(sum(bool(source.get("feedUrl") or source.get("feedUrls") or source.get("endpoints")) for source in sources), 4)
        for source in sources:
            self.assertTrue(source["url"].startswith("https://"), source["id"])
            self.assertGreaterEqual(float(source["trust"]), 0.8)
            self.assertLessEqual(float(source["trust"]), 1.0)
            self.assertIn(source.get("adapter", "auto"), {"auto", "html", "json", "jsonld", "localist", "trumba", "rss", "atom", "xml", "ics", "ical", "icalendar"})

    def test_static_builder(self):
        env = dict(os.environ, GITHUB_REPOSITORY="TheAgencyMGE/nextup-pnw")
        stale = ROOT / "docs" / "opportunities" / "stale-generated-page" / "index.html"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("stale", encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_static.py")], cwd=ROOT, env=env, check=True, capture_output=True)
        index = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("NextUp PNW", index)
        self.assertIn("TheAgencyMGE/nextup-pnw/issues/new", index)
        self.assertIn("What’s next around Puget Sound", index)
        self.assertIn('class="opportunity-list"', index)
        self.assertIn('class="opportunity-row"', index)
        self.assertIn('id="reset-filters"', index)
        self.assertIn("View official listing", index)
        self.assertNotIn('class="hero-panel"', index)
        self.assertNotIn('class="opportunity-grid"', index)
        first_id = json.loads((ROOT / "data" / "opportunities.json").read_text(encoding="utf-8"))[0]["id"]
        self.assertTrue((ROOT / "docs" / "opportunities" / first_id / "index.html").exists())
        detail = (ROOT / "docs" / "opportunities" / first_id / "index.html").read_text(encoding="utf-8")
        self.assertIn("Open official listing", detail)
        self.assertIn('class="detail-facts"', detail)
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
