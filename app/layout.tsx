import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NextUp PNW — Student Opportunities Around Seattle",
  description: "Verified opportunities across medicine, law, business, engineering, arts, public service, research, and technology around the Puget Sound.",
  metadataBase: new URL("https://nextup-pnw.theagencymge.chatgpt.site"),
  openGraph: { title: "NextUp PNW", description: "Stop finding out after it happened. Find verified student opportunities across the Puget Sound.", type: "website", images: [{ url: "/og.png", width: 1731, height: 909, alt: "NextUp PNW — Stop finding out after it happened." }] },
  twitter: { card: "summary_large_image", title: "NextUp PNW", description: "Verified cross-field opportunities across the Puget Sound.", images: ["/og.png"] },
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
