import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import opportunities from "@/data/opportunities.json";

const submitUrl = "https://github.com/TheAgencyMGE/nextup-pnw/issues/new?template=submit-opportunity.yml";

export function generateStaticParams() {
  return opportunities.map((item) => ({ id: item.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const item = opportunities.find((opportunity) => opportunity.id === id);
  if (!item) return { title: "Opportunity not found — NextUp PNW" };
  const canonical = `/opportunities/${item.id}/`;
  return {
    title: `${item.title} — NextUp PNW`,
    description: item.description,
    alternates: { canonical },
    openGraph: { title: `${item.title} — NextUp PNW`, description: item.description, type: "website", url: canonical },
    twitter: { card: "summary_large_image", title: `${item.title} — NextUp PNW`, description: item.description },
  };
}

function formatDate(start: string, end: string | null) {
  const first = new Date(`${start}T12:00:00-07:00`);
  const options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", year: "numeric" };
  if (!end || end === start) return first.toLocaleDateString("en-US", options);
  const last = new Date(`${end}T12:00:00-07:00`);
  return `${first.toLocaleDateString("en-US", options)}–${last.toLocaleDateString("en-US", options)}`;
}

export default async function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const item = opportunities.find((opportunity) => opportunity.id === id);
  if (!item) notFound();
  const officialUrl = item.registrationUrl || item.sourceUrl;
  const eventJsonLd = {
    "@context": "https://schema.org",
    "@type": "Event",
    name: item.title,
    description: item.description,
    startDate: item.startDate,
    endDate: item.endDate || item.startDate,
    eventAttendanceMode: item.format === "Online" ? "https://schema.org/OnlineEventAttendanceMode" : "https://schema.org/OfflineEventAttendanceMode",
    eventStatus: "https://schema.org/EventScheduled",
    location: { "@type": "Place", name: item.venue, address: { "@type": "PostalAddress", addressLocality: item.city, addressRegion: "WA", addressCountry: "US" } },
    organizer: { "@type": "Organization", name: item.organizer, url: item.sourceUrl },
    url: officialUrl,
  };

  return (
    <main>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(eventJsonLd).replace(/</g, "\\u003c") }} />
      <header className="site-header">
        <Link className="brand" href="/" aria-label="NextUp PNW home"><span className="brand-mark" aria-hidden="true">N<span>↗</span></span><span>NextUp <em>PNW</em></span></Link>
        <nav aria-label="Main navigation"><Link href="/#opportunities">Directory</Link><Link href="/#method">How listings are checked</Link><a className="submit-nav" href={submitUrl} target="_blank" rel="noreferrer">Send an official link</a></nav>
      </header>

      <section className="detail-page">
        <Link className="back-link" href="/#opportunities">← Back to the directory</Link>
        <div className="detail-layout">
          <article className="detail-content">
            <div className="detail-flags"><span className={`status status-${item.status}`}>{item.status}</span><span className="field-label">{item.field}</span><span className="verified">Checked {item.verifiedAt}</span></div>
            <h1>{item.title}</h1>
            <p className="detail-organizer">{item.organizer}</p>
            <p className="detail-deck">{item.description}</p>
            <section className="why-section" aria-labelledby="why-title"><h2 id="why-title">Why it may be useful</h2><p>{item.whyItStandsOut}</p></section>
            <a className="official-link detail-action" href={officialUrl} target="_blank" rel="noreferrer">Open official listing <span aria-hidden="true">↗</span></a>
            <p className="source-note">Confirm final dates, eligibility, and registration requirements with the organizer.</p>
          </article>
          <aside className="detail-facts" aria-label="Opportunity details">
            <p className="facts-heading">At a glance</p>
            <dl>
              <div><dt>Date</dt><dd>{formatDate(item.startDate, item.endDate)}</dd></div>
              <div><dt>Location</dt><dd>{item.venue}</dd></div>
              <div><dt>Eligibility</dt><dd>{item.eligibility}</dd></div>
              <div><dt>Type</dt><dd>{item.type}</dd></div>
              <div><dt>Cost</dt><dd>{item.cost}</dd></div>
              <div><dt>Format</dt><dd>{item.format}</dd></div>
            </dl>
          </aside>
        </div>
      </section>

      <footer><div className="brand footer-brand"><span className="brand-mark" aria-hidden="true">N<span>↗</span></span><span>NextUp <em>PNW</em></span></div><p>Student opportunities around Puget Sound, sorted by what’s next.</p><div><Link href="/">Home</Link><a href={submitUrl} target="_blank" rel="noreferrer">Submit a link</a></div></footer>
    </main>
  );
}
