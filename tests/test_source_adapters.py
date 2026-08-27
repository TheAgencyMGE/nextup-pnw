import sys
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))

from source_adapters import AdapterError, extract_records


class SourceAdapterTests(unittest.TestCase):
    def fixture(self, name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    def test_extracts_localist_json_wrapper(self):
        records = extract_records(
            self.fixture("events.json"),
            "application/json",
            "https://events.example.edu/api/2/events",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Seattle Student Data Workshop")
        self.assertEqual(records[0]["startDate"], "2099-09-14T17:00:00-07:00")
        self.assertEqual(records[0]["location"]["address"]["addressLocality"], "Seattle")
        self.assertEqual(records[0]["url"], "https://events.example.edu/event/data-workshop")

    def test_extracts_trumba_json_fields(self):
        records = extract_records(
            self.fixture("events-trumba.json"),
            "application/json",
            "https://www.trumba.com/calendars/sea_campus.json",
            adapter="trumba",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "UW Seattle Teaching Technologies Workshop")
        self.assertEqual(records[0]["startDate"], "2099-08-24T11:00:00")
        self.assertEqual(records[0]["endDate"], "2099-08-24T12:00:00")
        self.assertEqual(records[0]["location"], "Online")
        self.assertIn("eventid%3D204112777", records[0]["url"])

    def test_extracts_wordpress_tribe_events(self):
        payload = json.dumps({
            "events": [{
                "title": "UBC Student Research Workshop",
                "description": "A hands-on research workshop for students.",
                "start_date": "2099-09-14 10:00:00",
                "end_date": "2099-09-14 12:00:00",
                "url": "https://events.ubc.ca/event/research-workshop/",
                "venue": {"venue": "Koerner Library", "city": "Vancouver", "province": "British Columbia"},
                "organizer": [{"organizer": "UBC Library"}],
                "cost": "Free",
            }]
        })
        records = extract_records(payload, "application/json", "https://events.ubc.ca/", adapter="tribe")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "UBC Student Research Workshop")
        self.assertEqual(records[0]["startDate"], "2099-09-14 10:00:00")
        self.assertEqual(records[0]["location"]["address"]["addressLocality"], "Vancouver")
        self.assertEqual(records[0]["location"]["address"]["addressRegion"], "British Columbia")
        self.assertEqual(records[0]["organizer"], {"name": "UBC Library"})
        self.assertEqual(records[0]["offers"], {"price": "0", "priceCurrency": "CAD"})

    def test_extracts_rss_with_namespaced_or_plain_event_fields(self):
        records = extract_records(
            self.fixture("events.xml"),
            "application/rss+xml",
            "https://careers.example.edu/feed.xml",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Tacoma Engineering Career Fair")
        self.assertEqual(records[0]["startDate"], "2099-10-12T10:00:00-07:00")
        self.assertEqual(records[0]["url"], "https://careers.example.edu/events/engineering-career-fair")

    def test_extracts_icalendar_and_unescapes_values(self):
        records = extract_records(
            self.fixture("events.ics"),
            "text/calendar",
            "https://bellevue.example.gov/calendar.ics",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Bellevue Youth Mentorship Orientation")
        self.assertEqual(records[0]["startDate"], "2099-11-03")
        self.assertEqual(records[0]["location"], "Bellevue Library, Bellevue, WA")
        self.assertEqual(records[0]["url"], "https://bellevue.example.gov/events/youth-mentorship")

    def test_extracts_conservative_html_event_cards(self):
        records = extract_records(
            self.fixture("events.html"),
            "text/html",
            "https://www.example.org/calendar",
            adapter="html",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Research Poster Workshop")
        self.assertEqual(records[0]["startDate"], "2099-11-08T15:00:00-08:00")
        self.assertEqual(records[0]["url"], "https://www.example.org/events/research-poster-workshop")
        self.assertIn("Seattle", records[0]["location"])

    def test_malformed_payload_is_reported(self):
        with self.assertRaisesRegex(AdapterError, "malformed JSON"):
            extract_records("not valid", "application/json", "https://example.org/feed")

    def test_unsupported_adapter_is_reported(self):
        with self.assertRaisesRegex(AdapterError, "unsupported adapter"):
            extract_records("anything", "text/plain", "https://example.org/feed", adapter="proprietary")

    def test_malformed_xml_is_reported(self):
        with self.assertRaisesRegex(AdapterError, "malformed XML"):
            extract_records("<rss><broken>", "application/rss+xml", "https://example.org/feed")

    def test_malformed_icalendar_is_reported(self):
        with self.assertRaisesRegex(AdapterError, "malformed iCalendar"):
            extract_records("not a calendar", "text/calendar", "https://example.org/feed")


if __name__ == "__main__":
    unittest.main()
