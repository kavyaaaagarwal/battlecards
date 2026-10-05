import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import "./report.css";

export const metadata: Metadata = {
  title: "Battlecards",
  description: "Cited competitive battlecards, researched live by an AI agent with source-quality rules.",
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
