# NextUp PNW

**Stop finding out after it happened.**

NextUp PNW is a verified directory of internships, workshops, competitions, research, conferences, mentorship, and leadership programs that people around the Puget Sound can actually join. It covers medicine and health, law and civic work, business, engineering and science, arts and media, public service, career development, and technology.

The service is built as a zero-backend GitHub Pages site. Public browsing requires no account. Scheduled GitHub Actions verify existing listings every day, search monitored sources every Sunday, archive expired opportunities, rebuild the site, and deploy the result.

## What ships

- Mobile-first searchable directory
- Filters for career field, location, search, and beginner accessibility
- Individual SEO-friendly event pages with Schema.org `Event` data
- More than 100 active opportunities across eight career fields after the initial live-source refresh
- Forty-three monitored regional sources, prioritizing official organizers
- Multi-format discovery from JSON-LD, JSON calendar APIs, RSS/Atom, iCalendar, and structured HTML
- Conservative automatic publishing based on location, relevance, recency, source confidence, and calendar-noise rejection
- Duplicate detection and automatic expiration
- Community submission form powered by GitHub Issue Forms
- Automatic validation and publication of high-confidence submissions
- Automated tests and Pages deployment
- No analytics, advertising, cookies, accounts, API keys, or paid services

## Coverage

NextUp PNW prioritizes Bothell, Seattle, Bellevue, Redmond, Everett, Tacoma, Kirkland, Renton, Shoreline, Lynnwood, Woodinville, and the surrounding Puget Sound region.

## How updates work

1. `scripts/verify.py` checks published source links and archives finished listings.
2. `scripts/discover.py` reads enabled sources from `config/sources.json`, respects `robots.txt`, rate-limits requests, extracts structured event data, and applies publication rules.
3. `scripts/build_static.py` regenerates the directory, detail pages, sitemap, social metadata, and GitHub Pages output in `docs/`.
4. `.github/workflows/update-opportunities.yml` commits meaningful updates and deploys the refreshed site.

The collector does not bypass access controls, scrape private communities, or pretend that low-confidence data has been verified. Breadth comes from monitoring many kinds of official sources, not from lowering the publication threshold.

## Community submissions

The **Submit an opportunity** button opens a structured GitHub Issue Form. The submission workflow checks the official URL, reads machine-readable event details, applies the same geographic and relevance rules, detects duplicates, and publishes high-confidence matches. Ambiguous submissions stay open with a clear explanation rather than being silently published.

## Launch from a phone

Follow [PHONE_SETUP.md](PHONE_SETUP.md). It covers the complete one-commit launch, GitHub Pages settings, automation permissions, first deployment, submission testing, and troubleshooting without requiring a computer.

## Local commands

The production pipeline requires only Python 3.11 or newer and uses the standard library.

```bash
python scripts/build_static.py
python -m unittest discover -s tests -p 'test_*.py'
python scripts/verify.py --dry-run
python scripts/discover.py --dry-run
```

Open `docs/index.html` through a local web server to inspect the GitHub Pages build:

```bash
python -m http.server 8000 --directory docs
```

## Repository map

```text
.github/                 Issue forms and automation workflows
config/sources.json      Monitored sources and trust settings
data/                    Canonical listings, archive, and run status
docs/                    Generated GitHub Pages website
public/                  Brand assets used by the builder
scripts/                 Discovery, verification, submission, and build code
static/                  Website templates and browser interactions
tests/                   Pipeline tests
```

## Add or disable a source

Edit `config/sources.json`. Every source has an `enabled` switch, trust score, crawl limit, and official URL. Disabling a source preserves existing listings but stops future discovery from it.

## Safety and accuracy

- Every listing links to an external organizer; NextUp PNW is not the organizer.
- Dates, costs, and rules can change. Visitors are told to confirm final details before making plans.
- Collection uses an identified user agent, checks `robots.txt`, limits page size, and pauses between same-domain requests.
- Submitted resources are never published solely because somebody submitted them.
- The project contains no secrets. GitHub's temporary workflow token supplies only the permissions declared by each workflow.

## License

MIT. See [LICENSE](LICENSE).
