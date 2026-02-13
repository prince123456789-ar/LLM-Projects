import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Real Estate AI SaaS", description: "AI-powered lead management for real estate agencies" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body>
      <header className="topbar"><div className="container row topbar-inner">
        <Link href="/" className="brand">RealEstateAI</Link>
        <nav className="nav-links">
          <Link href="/dashboard">Dashboard</Link><Link href="/leads">Leads</Link><Link href="/integrations">Integrations</Link><Link href="/appointments">Appointments</Link><Link href="/reports">Reports</Link><Link href="/pricing">Pricing</Link><Link href="/login">Login</Link>
        </nav>
      </div></header>
      {children}
      <footer className="site-footer"><div className="container row footer-inner"><p className="small">(c) {new Date().getFullYear()} RealEstateAI</p><div className="row" style={{ gap: "12px" }}><Link href="/pricing" className="small">Pricing</Link><Link href="/terms" className="small">Terms</Link><Link href="/privacy" className="small">Privacy</Link></div></div></footer>
    </body></html>
  );
}