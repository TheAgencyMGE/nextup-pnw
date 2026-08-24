"use client";

import { useMemo, useState } from "react";
import opportunities from "@/data/opportunities.json";

type Opportunity = (typeof opportunities)[number];

const cities = ["All locations", ...Array.from(new Set(opportunities.map((item) => item.city)))];
const fields = ["All fields", ...Array.from(new Set(opportunities.map((item) => item.field)))];
const featured = [...opportunities].filter((item) => item.status !== "closed").sort((a, b) => a.startDate.localeCompare(b.startDate))[0];

function formatDate(start: string, end: string | null) {
  const first = new Date(`${start}T12:00:00-07:00`);
  const options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  if (!end || end === start) return first.toLocaleDateString("en-US", options);
  const last = new Date(`${end}T12:00:00-07:00`);
  return `${first.toLocaleDateString("en-US", options)}–${last.toLocaleDateString("en-US", options)}`;
}

function daysUntil(date: string) {
  const today = new Date();
  const target = new Date(`${date}T23:59:59-07:00`);
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000);
}

function OpportunityCard({ item }: { item: Opportunity }) {
  const deadlineDays = item.deadline ? daysUntil(item.deadline) : null;
  return (
    <article className="opportunity-card">
      <div className="card-topline">
        <span className={`status status-${item.status}`}>{item.status.replace("_", " ")}</span>
        <span className="verified" title={`Last checked ${item.verifiedAt}`}><span aria-hidden="true">✓</span> Verified</span>
      </div>
      <div className="date-block" aria-label={`Runs ${formatDate(item.startDate, item.endDate)}`}>
        <strong>{formatDate(item.startDate, item.endDate)}</strong><span>{item.startDate.slice(0, 4)}</span>
      </div>
      <h3>{item.title}</h3>
      <p className="organizer">{item.organizer}</p>
      <p className="card-description">{item.description}</p>
      <div className="tag-row" aria-label="Opportunity details">
        <span className="field-tag">{item.field}</span><span>{item.city}</span><span>{item.type}</span><span>{item.cost}</span>
        {item.beginnerFriendly && <span className="beginner">Beginner-friendly</span>}
      </div>
      <div className="standout"><span aria-hidden="true">↗</span><p><strong>Why it stands out</strong>{item.whyItStandsOut}</p></div>
      <div className="card-footer">
        <div><span className="footer-label">Eligibility</span><p>{item.eligibility}</p></div>
        {item.deadline && <div className="deadline"><span className="footer-label">Deadline</span><p>{deadlineDays !== null && deadlineDays >= 0 ? `${deadlineDays} days left` : item.deadline}</p></div>}
      </div>
      <a className="primary-link" href={item.registrationUrl || item.sourceUrl} target="_blank" rel="noreferrer">View official page <span aria-hidden="true">↗</span></a>
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
    return opportunities.filter((item) => item.status !== "closed")
      .filter((item) => city === "All locations" || item.city === city)
      .filter((item) => field === "All fields" || item.field === field)
      .filter((item) => !beginnerOnly || item.beginnerFriendly)
      .filter((item) => !search || [item.title, item.organizer, item.field, item.city, item.type, item.description, ...item.tags].join(" ").toLowerCase().includes(search))
      .sort((a, b) => a.startDate.localeCompare(b.startDate));
  }, [query, city, field, beginnerOnly]);

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="NextUp PNW home"><span className="brand-mark" aria-hidden="true">N<span>↗</span></span><span>NextUp <em>PNW</em></span></a>
        <nav aria-label="Main navigation"><a href="#opportunities">Explore</a><a href="#how-it-works">How it works</a><a className="submit-nav" href="https://github.com/TheAgencyMGE/nextup-pnw/issues/new?template=submit-opportunity.yml" target="_blank" rel="noreferrer">Submit an opportunity</a></nav>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span></span> Puget Sound&apos;s student opportunity radar</p>
          <h1>Stop finding out<br /><i>after</i> it happened.</h1>
          <p className="hero-deck">Verified internships, workshops, competitions, conferences, research, and leadership programs across every field—not only tech.</p>
          <div className="hero-actions"><a className="hero-primary" href="#opportunities">See what&apos;s next <span aria-hidden="true">↓</span></a><a className="hero-secondary" href="https://github.com/TheAgencyMGE/nextup-pnw/issues/new?template=submit-opportunity.yml" target="_blank" rel="noreferrer">Found one we missed?</a></div>
          <div className="trust-row" aria-label="Service highlights"><span><b>✓</b> {opportunities.length} researched listings</span><span><b>✓</b> 8 career fields</span><span><b>✓</b> No account needed to browse</span></div>
        </div>
        <div className="hero-panel" aria-label="Next opportunity preview">
          <div className="panel-grid"></div><p className="panel-kicker">NEXT UP</p><div className="big-date"><strong>{new Date(`${featured.startDate}T12:00:00`).getDate()}</strong><span>{new Date(`${featured.startDate}T12:00:00`).toLocaleDateString("en-US", { month: "short" }).toUpperCase()}<br />{featured.startDate.slice(0, 4)}</span></div>
          <div className="panel-event"><p>{featured.title}</p><span>{featured.field} · {featured.city}</span></div><div className="panel-orbit orbit-one"></div><div className="panel-orbit orbit-two"></div><div className="panel-arrow">↗</div>
        </div>
      </section>

      <section className="ticker" aria-label="Career fields"><div>MEDICINE &amp; HEALTH <span>✦</span> LAW &amp; CIVIC <span>✦</span> BUSINESS <span>✦</span> ENGINEERING <span>✦</span> ARTS &amp; MEDIA <span>✦</span> TECHNOLOGY <span>✦</span></div></section>

      <section className="opportunities-section" id="opportunities">
        <div className="section-heading"><div><p className="eyebrow"><span></span> Recently verified</p><h2>Opportunities worth<br />showing up for.</h2></div><p>Small events, major programs, and everything useful in between. Every listing links directly to its organizer.</p></div>
        <div className="filter-bar" role="search">
          <label className="search-box"><span className="sr-only">Search opportunities</span><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search opportunities…" /></label>
          <label><span className="sr-only">Filter by location</span><select value={city} onChange={(event) => setCity(event.target.value)}>{cities.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label><span className="sr-only">Filter by field</span><select value={field} onChange={(event) => setField(event.target.value)}>{fields.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label className="toggle-label"><input type="checkbox" checked={beginnerOnly} onChange={(event) => setBeginnerOnly(event.target.checked)} /><span className="toggle" aria-hidden="true"></span>Beginner-friendly</label>
        </div>
        <div className="result-count"><strong>{filtered.length}</strong> upcoming opportunities</div>
        {filtered.length ? <div className="opportunity-grid">{filtered.map((item) => <OpportunityCard item={item} key={item.id} />)}</div> : <div className="empty-state"><strong>No exact matches yet.</strong><p>Try clearing a filter—or submit an opportunity we should know about.</p></div>}
      </section>

      <section className="how-section" id="how-it-works">
        <div><p className="eyebrow light"><span></span> Built for trust</p><h2>Useful beats<br />overwhelming.</h2><p>NextUp PNW monitors official calendars and community sources, checks the important details, and removes expired listings automatically.</p></div>
        <ol><li><span>01</span><div><strong>Discover</strong><p>We monitor schools, hospitals, law programs, business groups, museums, governments, nonprofits, and engineering and technology communities.</p></div></li><li><span>02</span><div><strong>Verify</strong><p>Dates, eligibility, location, cost, and official links are checked before publication.</p></div></li><li><span>03</span><div><strong>Keep current</strong><p>Finished opportunities disappear from the main directory, while new ones arrive every week.</p></div></li></ol>
      </section>

      <section className="submit-section"><div><p className="eyebrow"><span></span> Community powered</p><h2>The best opportunities<br />often start small.</h2></div><div><p>Know about an internship, pre-med program, law event, business competition, engineering team, arts workshop, or community resource we missed? Send the official link. The verification system handles the rest.</p><a className="hero-primary dark" href="https://github.com/TheAgencyMGE/nextup-pnw/issues/new?template=submit-opportunity.yml" target="_blank" rel="noreferrer">Submit a resource <span aria-hidden="true">↗</span></a></div></section>

      <footer><div className="brand footer-brand"><span className="brand-mark" aria-hidden="true">N<span>↗</span></span><span>NextUp <em>PNW</em></span></div><p>Built for students who refuse to hear “you should&apos;ve applied” one week too late.</p><div><a href="https://github.com/TheAgencyMGE/nextup-pnw" target="_blank" rel="noreferrer">GitHub</a><a href="#how-it-works">Methodology</a><a href="https://github.com/TheAgencyMGE/nextup-pnw/issues/new?template=submit-opportunity.yml" target="_blank" rel="noreferrer">Submit</a></div></footer>
    </main>
  );
}
