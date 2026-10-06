import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import "./report.css";

export const metadata: Metadata = {
  title: "Battlecards",
  description: "Enter your company and competitors. The agent researches public sources and builds concise, source-linked battlecards for your sales team.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="wrap">
          <nav className="site-nav">
            <Link href="/" className="brand">Battlecards</Link>
            <Link href="/reports">All reports</Link>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
