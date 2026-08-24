import json
import os
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from opportunity_utils import dedupe_key, extract_jsonld, qualifies, schema_to_opportunity, unique_opportunity_id


class PipelineTests(unittest.TestCase):
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

    def test_dedupe_normalizes_year(self):
        left = {"title":"Example Hackathon 2026","startDate":"2026-10-01"}
        right = {"title":"Example Hackathon","startDate":"2026-10-01"}
        self.assertEqual(dedupe_key(left), dedupe_key(right))

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
        data = json.loads((ROOT / "data" / "opportunities.json").read_text())
        required = {"id","title","organizer","field","type","city","startDate","status","eligibility","sourceUrl","verifiedAt"}
        self.assertGreaterEqual(len(data), 35)
        self.assertGreaterEqual(len({item["field"] for item in data}), 8)
        self.assertEqual(len({item["id"] for item in data}), len(data))
        for item in data:
            self.assertFalse(required - item.keys())

    def test_static_builder(self):
        env = dict(os.environ, GITHUB_REPOSITORY="TheAgencyMGE/nextup-pnw")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_static.py")], cwd=ROOT, env=env, check=True, capture_output=True)
        index = (ROOT / "docs" / "index.html").read_text()
        self.assertIn("NextUp PNW", index)
        self.assertIn("TheAgencyMGE/nextup-pnw/issues/new", index)
        self.assertTrue((ROOT / "docs" / "opportunities" / "frontier-cascadia-2026" / "index.html").exists())


if __name__ == "__main__":
    unittest.main()