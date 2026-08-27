import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NextUp PNW — Student Opportunities Across the Pacific Northwest",
  description: "Internships, workshops, fairs, competitions, research programs, and student events across Washington, Oregon, Idaho, and British Columbia.",
  metadataBase: new URL("https://nextup-pnw.theagencymge.chatgpt.site"),
  openGraph: { title: "NextUp PNW", description: "What’s next across the Pacific Northwest: student opportunities sorted by date and tied to official sources.", type: "website", images: [{ url: "/og.png", width: 1731, height: 909, alt: "NextUp PNW student opportunity directory" }] },
  twitter: { card: "summary_large_image", title: "NextUp PNW", description: "Student opportunities across the Pacific Northwest, sorted by what’s next.", images: ["/og.png"] },
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
