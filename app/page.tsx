"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import opportunities from "@/data/opportunities.json";

type Opportunity = (typeof opportunities)[number];

const submitUrl = "https://github.com/TheAgencyMGE/nextup-pnw/issues/new?template=submit-opportunity.yml";
const cities = ["All locations", ...Array.from(new Set(opportunities.map((item) => item.city))).sort()];
const fields = ["All fields", ...Array.from(new Set(opportunities.map((item) => item.field))).sort()];

function formatDate(start: string, end: string | null) {
  const first = new Date(`${start}T12:00:00-07:00`);
  const short: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  if (!end || end === start) return first.toLocaleDateString("en-US", short);
  const last = new Date(`${end}T12:00:00-07:00`);
  return `${first.toLocaleDateString("en-US", short)}–${last.toLocaleDateString("en-US", short)}`;
}

function OpportunityRow({ item }: { item: Opportunity }) {
  const officialUrl = item.registrationUrl || item.sourceUrl;
  return (
    <article className="opportunity-row">
      <div className="date-rail">
        <time dateTime={item.startDate}>{formatDate(item.startDate, item.endDate)}</time>
        <span>{item.startDate.slice(0, 4)}</span>
      </div>
      <div className="row-main">
        <div className="row-flags">
          <span className={`status status-${item.status}`}>{item.status.replace("_", " ")}</span>
          <span className="field-label">{item.field}</span>
          {item.beginnerFriendly && <span className="beginner-label">Beginner-friendly</span>}
        </div>
        <h3><Link href={`/opportunities/${item.id}/`}>{item.title}</Link></h3>
        <p className="organizer">{item.organizer}</p>
        <p className="row-description">{item.description}</p>
        <dl className="row-details">
          <div><dt>Location</dt><dd>{item.city}</dd></div>
          <div><dt>Format</dt><dd>{item.format}</dd></div>
          <div><dt>Type</dt><dd>{item.type}</dd></div>
          <div><dt>Cost</dt><dd>{item.cost}</dd></div>
        </dl>
        <p className="eligibility"><strong>Eligibility:</strong> {item.eligibility}</p>
      </div>
      <div className="row-action">
        {item.deadline && <p className="deadline-note"><span>Apply by</span>{formatDate(item.deadline, item.deadline)}</p>}
        <a className="official-link" href={officialUrl} target="_blank" rel="noreferrer">View official listing <span aria-hidden="true">↗</span></a>
        <Link className="detail-link" href={`/opportunities/${item.id}/`}>Read details</Link>
        <span className="verified">Checked {item.verifiedAt}</span>
      </div>
    </article>
  );
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("All locations");
  const [field, setField] = useState("All fields");
  const [beginnerOnly, setBeginnerOnly] = useState(false);

  const filtered = useMemo(() => {
    const search = query.trim().toLowerCase();
    return opportunities
      .filter((item) => item.status !== "closed")
      .filter((item) => city === "All locations" || item.city === city)
      .filter((item) => field === "All fields" || item.field === field)
      .filter((item) => !beginnerOnly || item.beginnerFriendly)
      .filter((item) => !search || [item.title, item.organizer, item.field, item.city, item.type, item.description, ...item.tags].join(" ").toLowerCase().includes(search))
      .sort((a, b) => a.startDate.localeCompare(b.startDate));
  }, [query, city, field, beginnerOnly]);

  const hasFilters = Boolean(query || city !== "All locations" || field !== "All fields" || beginnerOnly);
  const resetFilters = () => {
    setQuery("");
    setCity("All locations");
    setField("All fields");
    setBeginnerOnly(false);
  };

  return (
    <main id="top">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="NextUp PNW home"><span className="brand-mark" aria-hidden="true">N<span>↗</span></span><span>NextUp <em>PNW</em></span></a>
        <nav aria-label="Main navigation"><a href="#opportunities">Directory</a><a href="#method">How listings are checked</a><a className="submit-nav" href={submitUrl} target="_blank" rel="noreferrer">Send an official link</a></nav>
      </header>

      <section className="intro" aria-labelledby="intro-title">
        <div>
          <p className="context-line">Puget Sound · Student opportunity directory</p>
          <h1 id="intro-title">What’s next around Puget Sound.</h1>
          <p className="intro-copy">Find internships, workshops, career fairs, competitions, research programs, and community events before the date passes. Every result links to its organizer.</p>
          <a className="jump-link" href="#opportunities">Browse opportunities <span aria-hidden="true">↓</span></a>
        </div>
        <aside className="directory-brief" aria-label="Directory summary">
          <p className="brief-count"><strong>{opportunities.length}</strong><span>active listings</span></p>
          <p>Across {fields.length - 1} fields and {cities.length - 1} Puget Sound locations.</p>
          <p className="kept-line">Stop finding out after it happened.</p>
        </aside>
      </section>

      <section className="opportunities-section" id="opportunities" aria-labelledby="directory-title">
        <div className="directory-heading"><div><p className="section-index">Directory / Updated weekly</p><h2 id="directory-title">Upcoming opportunities</h2></div><p>Sorted by start date. Use the filters to narrow the list.</p></div>
        <div className="filter-bar" role="search" aria-label="Filter opportunities">
          <label className="search-field"><span>Search</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Title, organizer, or keyword" /></label>
          <label><span>Location</span><select value={city} onChange={(event) => setCity(event.target.value)}>{cities.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label><span>Field</span><select value={field} onChange={(event) => setField(event.target.value)}>{fields.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label className="check-label"><input type="checkbox" checked={beginnerOnly} onChange={(event) => setBeginnerOnly(event.target.checked)} /><span>Beginner-friendly only</span></label>
          <button className="reset-button" type="button" onClick={resetFilters} disabled={!hasFilters}>Reset filters</button>
        </div>
        <div className="result-summary" aria-live="polite"><strong>{filtered.length}</strong> {filtered.length === 1 ? "listing" : "listings"}</div>
        {filtered.length ? <div className="opportunity-list">{filtered.map((item) => <OpportunityRow item={item} key={item.id} />)}</div> : <div className="empty-state"><strong>No listings match those filters.</strong><p>Reset the directory or send an official opportunity link for review.</p><div><button type="button" onClick={resetFilters}>Reset filters</button><a href={submitUrl} target="_blank" rel="noreferrer">Send an official link</a></div></div>}
      </section>

      <section className="method-section" id="method" aria-labelledby="method-title">
        <div className="method-lead"><p className="section-index">How the directory works</p><h2 id="method-title">Useful details, tied to a source.</h2></div>
        <dl className="method-list">
          <div><dt>Collected</dt><dd>Official calendars and organizer pages across schools, governments, nonprofits, hospitals, museums, and industry groups.</dd></div>
          <div><dt>Checked</dt><dd>Date, location, eligibility, cost, and a working organizer link are required before a listing appears.</dd></div>
          <div><dt>Kept current</dt><dd>Past opportunities leave the active directory. New and updated records are merged without erasing valid listings from partial feeds.</dd></div>
        </dl>
      </section>

      <section className="submit-section" aria-labelledby="submit-title">
        <div><p className="section-index">Missing something?</p><h2 id="submit-title">Send the organizer’s link.</h2></div>
        <div><p>Share the official page for a Puget Sound internship, program, competition, workshop, fair, or student event. We’ll check the details before it appears here.</p><a className="submit-link" href={submitUrl} target="_blank" rel="noreferrer">Send an official link <span aria-hidden="true">↗</span></a></div>
      </section>

      <footer><div className="brand footer-brand"><span className="brand-mark" aria-hidden="true">N<span>↗</span></span><span>NextUp <em>PNW</em></span></div><p>Student opportunities around Puget Sound, sorted by what’s next.</p><div><a href="https://github.com/TheAgencyMGE/nextup-pnw" target="_blank" rel="noreferrer">GitHub</a><a href="#method">Method</a><a href={submitUrl} target="_blank" rel="noreferrer">Submit a link</a></div></footer>
    </main>
  );
}
