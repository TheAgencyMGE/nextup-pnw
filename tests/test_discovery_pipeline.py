import json
import sys
import threading
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))

from discovery_pipeline import collect_source, collect_sources, limit_opportunities, merge_opportunities, retain_existing


class DiscoveryPipelineTests(unittest.TestCase):
    def test_global_limit_preserves_regional_coverage_before_filling_by_date(self):
        records = []
        for region, count in (("WA", 8), ("OR", 8), ("ID", 2), ("BC", 8)):
            for number in range(count):
                records.append({"id": f"{region}-{number}", "region": region, "startDate": f"2099-09-{number + 1:02d}", "title": f"{region} event {number}"})
        limited = limit_opportunities(records, maximum=12, minimum_per_region=2)
        self.assertEqual(len(limited), 12)
        counts = {region: sum(item["region"] == region for item in limited) for region in ("WA", "OR", "ID", "BC")}
        self.assertTrue(all(count >= 2 for count in counts.values()))

    def test_collect_sources_runs_concurrently_and_preserves_configuration_order(self):
        barrier = threading.Barrier(3, timeout=2)
        payload = (FIXTURES / "events.json").read_text(encoding="utf-8")

        def fetcher(_url):
            barrier.wait()
            return payload, "application/json"

        sources = [
            {"id": f"source-{number}", "name": "University of Washington Events", "url": f"https://events{number}.uw.edu/", "feedUrl": f"https://events{number}.uw.edu/feed", "adapter": "json", "trust": 0.97}
            for number in range(3)
        ]
        results = collect_sources(sources, fetcher, date(2099, 1, 1), workers=3)
        self.assertEqual([result.source_id for result in results], [source["id"] for source in sources])
        self.assertEqual([result.accepted for result in results], [1, 1, 1])

    def test_collects_explicit_feed_once_and_accounts_for_acceptance(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            return (FIXTURES / "events.json").read_text(encoding="utf-8"), "application/json"

        source = {
            "id": "uw-test",
            "name": "University of Washington Test Events",
            "url": "https://events.example.edu/",
            "feedUrl": "https://events.example.edu/api/2/events",
            "adapter": "localist",
            "trust": 0.97,
        }
        result = collect_source(source, fetcher, date(2099, 1, 1))
        self.assertEqual(calls, [source["feedUrl"]])
        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.parsed, 1)
        self.assertEqual(result.accepted, 1)
        self.assertEqual(result.rejected, 0)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.items[0]["organizer"], source["name"])
        self.assertEqual(result.items[0]["sourceUrl"], source["url"])
        self.assertEqual(result.items[0]["sourceId"], source["id"])

    def test_one_endpoint_failure_does_not_discard_successful_endpoint(self):
        feed = (FIXTURES / "events.json").read_text(encoding="utf-8")

        def fetcher(url):
            if url.endswith("broken.json"):
                raise OSError("temporary upstream failure")
            return feed, "application/json"

        source = {
            "id": "uw-test",
            "name": "University of Washington Test Events",
            "url": "https://events.example.edu/",
            "feedUrls": [
                "https://events.example.edu/broken.json",
                "https://events.example.edu/events.json",
            ],
            "adapter": "localist",
            "trust": 0.97,
        }
        result = collect_source(source, fetcher, date(2099, 1, 1))
        self.assertEqual(result.accepted, 1)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("temporary upstream failure", result.failures[0]["error"])
        self.assertEqual(result.health, "degraded")

    def test_malformed_feed_is_counted_as_a_failure(self):
        source = {
            "id": "broken-feed", "name": "UW Events", "url": "https://uw.edu/events",
            "feedUrl": "https://uw.edu/events.json", "adapter": "json", "trust": 0.97,
        }
        result = collect_source(source, lambda _: ("not-json", "application/json"), date(2099, 1, 1))
        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.parsed, 0)
        self.assertEqual(result.accepted, 0)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("malformed JSON", result.failures[0]["error"])
        self.assertEqual(result.health, "failed")
        self.assertTrue(result.required)

    def test_collects_rejection_reasons(self):
        payload = json.dumps({
            "events": [{"name": "Global Online Coding Workshop", "startDate": "2099-09-14", "description": "For students worldwide", "location": "Online", "url": "https://example.org/global"}]
        })
        source = {
            "id": "generic-test",
            "name": "Example Learning Company",
            "url": "https://example.org/",
            "feedUrl": "https://example.org/events.json",
            "adapter": "json",
            "trust": 0.97,
        }
        result = collect_source(source, lambda _: (payload, "application/json"), date(2099, 1, 1))
        self.assertEqual(result.parsed, 1)
        self.assertEqual(result.accepted, 0)
        self.assertEqual(result.rejected, 1)
        self.assertEqual(result.rejection_reasons, {"outside the coverage area": 1})

    def test_caps_repeated_instances_of_one_series(self):
        events = []
        for day in range(1, 13):
            events.append({
                "name": "Seattle Student Career Workshop",
                "startDate": f"2099-09-{day:02d}",
                "description": "A career workshop for students in Seattle.",
                "location": {"name": "Campus", "address": {"addressLocality": "Seattle", "addressRegion": "WA"}},
                "url": "https://example.edu/events/career-workshop",
            })
        source = {
            "id": "recurring-series",
            "name": "Seattle University Events",
            "url": "https://example.edu/events",
            "feedUrl": "https://example.edu/events.json",
            "adapter": "json",
            "trust": 0.97,
            "region": "WA",
        }
        result = collect_source(source, lambda _: (json.dumps({"events": events}), "application/json"), date(2099, 1, 1))
        self.assertEqual(result.accepted, 10)
        self.assertEqual(result.rejected, 2)
        self.assertEqual(result.rejection_reasons["recurrence limit exceeded"], 2)

    def test_caps_repeated_series_even_when_each_occurrence_has_a_distinct_url(self):
        events = [{
            "name": "Seattle Student Career Office Hours", "startDate": f"2099-09-{day:02d}",
            "description": "Career support for students in Seattle.", "location": "Online",
            "url": f"https://example.edu/events/office-hours-{day}",
        } for day in range(1, 13)]
        source = {"id":"series","name":"Seattle University","url":"https://example.edu/events","feedUrl":"https://example.edu/feed","adapter":"json","trust":0.97,"region":"WA"}
        result = collect_source(source, lambda _: (json.dumps({"events": events}), "application/json"), date(2099, 1, 1))
        self.assertEqual(result.accepted, 10)
        self.assertEqual(result.rejection_reasons["recurrence limit exceeded"], 2)

    def test_merge_preserves_existing_id_and_enriches_from_higher_confidence_record(self):
        existing = [{
            "id": "stable-page-id",
            "title": "Seattle Student Workshop 2099",
            "organizer": "Seattle Public Library",
            "startDate": "2099-10-03",
            "endDate": "2099-10-03",
            "description": "Short description",
            "sourceUrl": "https://spl.org/calendar",
            "registrationUrl": "https://spl.org/events/123?utm_source=old",
            "confidence": 0.9,
        }]
        discovered = [{
            "id": "generated-id",
            "title": "Seattle Student Workshop",
            "organizer": "Seattle Public Library",
            "startDate": "2099-10-03",
            "endDate": "2099-10-03",
            "description": "A detailed hands-on workshop for Seattle students.",
            "sourceUrl": "https://spl.org/calendar",
            "registrationUrl": "https://spl.org/events/123",
            "confidence": 0.99,
        }]
        merged = merge_opportunities(existing, discovered)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "stable-page-id")
        self.assertEqual(merged[0]["description"], discovered[0]["description"])

    def test_equal_confidence_refresh_prefers_newly_cleaned_source_record(self):
        existing = [{
            "id": "stable-page-id", "title": "Seattle Student Workshop", "organizer": "Seattle Library",
            "startDate": "2099-10-03", "sourceUrl": "https://spl.org/calendar",
            "registrationUrl": "https://spl.org/events/123", "description": "Old&amp;nbsp;text\\n", "confidence": 0.97,
        }]
        discovered = [{
            "id": "generated-id", "title": "Seattle Student Workshop", "organizer": "Seattle Library",
            "startDate": "2099-10-03", "sourceUrl": "https://spl.org/calendar",
            "registrationUrl": "https://spl.org/events/123", "description": "Old text", "confidence": 0.97,
        }]
        merged = merge_opportunities(existing, discovered)
        self.assertEqual(merged[0]["id"], "stable-page-id")
        self.assertEqual(merged[0]["description"], "Old text")

    def test_merge_assigns_unique_ids_and_sorts_deterministically(self):
        discovered = [
            {"id":"workshop-2099","title":"Z Workshop","organizer":"Seattle Org","startDate":"2099-12-01","sourceUrl":"https://seattle.org/z"},
            {"id":"workshop-2099","title":"A Workshop","organizer":"Tacoma Org","startDate":"2099-11-01","sourceUrl":"https://tacoma.org/a"},
        ]
        merged = merge_opportunities([], discovered)
        self.assertEqual([item["title"] for item in merged], ["A Workshop", "Z Workshop"])
        self.assertEqual(len({item["id"] for item in merged}), 2)

    def test_merge_collapses_syndicated_trumba_event_across_campus_calendars(self):
        records = [
            {"id":"first","title":"Improving Information Access for Scientific Documents","organizer":"UW Seattle Events","startDate":"2099-09-23","registrationUrl":"https://washington.edu/calendar/?trumbaEmbed=view%3Devent%26eventid%3D206882359","sourceUrl":"https://washington.edu/calendar/one"},
            {"id":"second","title":"Improving Information Access for Scientific Documents","organizer":"UW Tacoma Events","startDate":"2099-09-23","registrationUrl":"https://tacoma.uw.edu/calendar?trumbaEmbed=view%3Devent%26eventid%3D206882359","sourceUrl":"https://tacoma.uw.edu/calendar/two"},
        ]
        self.assertEqual(len(merge_opportunities([], records)), 1)
        self.assertEqual(len(merge_opportunities(records, [])), 1)

    def test_merge_collapses_same_organizer_title_and_date_across_registration_systems(self):
        records = [
            {"id":"first","title":"Fall On-Campus and Part-Time Job Fair","organizer":"Boise State University Events","startDate":"2099-08-26","registrationUrl":"https://events.boisestate.edu/event/job-fair","sourceUrl":"https://events.boisestate.edu"},
            {"id":"second","title":"Fall On-Campus and Part-Time Job Fair","organizer":"Boise State University Events","startDate":"2099-08-26","registrationUrl":"https://boisestate.campusgroups.com/rsvp?id=123","sourceUrl":"https://events.boisestate.edu"},
        ]
        self.assertEqual(len(merge_opportunities([], records)), 1)

    def test_merge_does_not_collapse_named_event_from_different_organizers(self):
        records = [
            {"id":"curated","title":"Hack Northwest","organizer":"Hack NW Group","startDate":"2099-10-05","sourceUrl":"https://eventbrite.com/hack-northwest"},
            {"id":"feed","title":"Hack Northwest","organizer":"Seattle Hackathons","startDate":"2099-10-05","sourceUrl":"https://meetup.com/hack-northwest"},
        ]
        self.assertEqual(len(merge_opportunities(records, [])), 2)

    def test_merge_does_not_collapse_same_named_sessions_in_distinct_cities(self):
        records = [
            {"id":"first","title":"Student Workshop","organizer":"Regional Library","city":"Seattle","format":"In person","startDate":"2099-10-05","registrationUrl":"https://library.org/events/one","sourceUrl":"https://library.org/events"},
            {"id":"second","title":"Student Workshop","organizer":"Regional Library","city":"Tacoma","format":"In person","startDate":"2099-10-05","registrationUrl":"https://library.org/events/two","sourceUrl":"https://library.org/events"},
        ]
        self.assertEqual(len(merge_opportunities(records, [])), 2)

    def test_merge_collapses_rows_that_are_indistinguishable_in_the_directory(self):
        records = [
            {"id":"first","title":"Teaching Technologies Office Hours","organizer":"UW","city":"Online","format":"Online","startDate":"2099-10-05","registrationUrl":"https://uw.edu/event/one","sourceUrl":"https://uw.edu/events"},
            {"id":"second","title":"Teaching Technologies Office Hours","organizer":"UW","city":"Online","format":"Online","startDate":"2099-10-05","registrationUrl":"https://uw.edu/event/two","sourceUrl":"https://uw.edu/events"},
        ]
        self.assertEqual(len(merge_opportunities(records, [])), 1)

    def test_merge_fills_missing_registration_url_from_source(self):
        existing = [{"id":"legacy","title":"Seattle Hackathon","organizer":"Seattle Tech","startDate":"2099-10-03","sourceUrl":"https://seattletech.org/hackathon","registrationUrl":None}]
        merged = merge_opportunities(existing, [])
        self.assertEqual(merged[0]["registrationUrl"], existing[0]["sourceUrl"])

    def test_merge_preserves_unmatched_records_from_partial_feeds(self):
        existing = [
            {"id":"stale","title":"Old Calendar Item","organizer":"UW","startDate":"2099-10-01","sourceUrl":"https://uw.edu/old","sourceId":"uw-feed"},
            {"id":"manual","title":"Curated Opportunity","organizer":"Local Org","startDate":"2099-10-02","sourceUrl":"https://local.org/manual"},
            {"id":"unavailable","title":"Source Currently Down","organizer":"Other Org","startDate":"2099-10-03","sourceUrl":"https://other.org/item","sourceId":"failed-feed"},
        ]
        discovered = [{"id":"fresh","title":"Fresh UW Workshop","organizer":"UW","startDate":"2099-10-04","sourceUrl":"https://uw.edu/fresh","sourceId":"uw-feed"}]
        merged = merge_opportunities(existing, discovered)
        self.assertEqual({item["id"] for item in merged}, {"stale", "manual", "unavailable", "fresh"})

    def test_existing_series_is_pruned_to_the_same_recurrence_limit(self):
        existing = []
        for day in range(1, 13):
            existing.append({
                "id": f"series-{day}",
                "title": "Seattle Student Career Workshop",
                "organizer": "Seattle University",
                "description": "A career workshop for students.",
                "city": "Seattle",
                "region": "WA",
                "venue": "Seattle Campus",
                "eligibility": "Students",
                "whyItStandsOut": "Career skill building",
                "startDate": f"2099-09-{day:02d}",
                "endDate": f"2099-09-{day:02d}",
                "confidence": 0.97,
                "sourceUrl": "https://example.edu/events",
                "registrationUrl": "https://example.edu/events/career-workshop",
                "sourceId": "series-source",
            })
        retained, reasons = retain_existing(existing, [{"id": "series-source", "enabled": True}], date(2099, 1, 1))
        self.assertEqual(len(retained), 10)
        self.assertEqual(reasons["recurrence limit exceeded"], 2)

    def test_existing_legacy_record_gets_an_explicit_region(self):
        legacy = {
            "id": "legacy-seattle",
            "title": "Seattle Student Career Workshop",
            "organizer": "Seattle University",
            "description": "A career&amp;nbsp;workshop for students.\\n",
            "city": "Puget Sound",
            "venue": "Seattle Campus",
            "eligibility": "Students",
            "whyItStandsOut": "Career skill building",
            "startDate": "2099-09-01",
            "endDate": "2099-09-01",
            "confidence": 0.97,
            "sourceUrl": "https://example.edu/events",
            "registrationUrl": "https://example.edu/events/career-workshop",
        }
        retained, reasons = retain_existing([legacy], [], date(2099, 1, 1))
        self.assertEqual(reasons, {})
        self.assertEqual(retained[0]["region"], "WA")
        self.assertEqual(retained[0]["description"], "A career workshop for students.")


if __name__ == "__main__":
    unittest.main()
