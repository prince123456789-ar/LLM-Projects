import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Real Estate AI SaaS",
  description: "AI-powered lead management for real estate agencies"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <div className="container row topbar-inner" style={{ justifyContent: "space-between" }}>
            <Link href="/" className="brand">RealEstateAI</Link>
            <nav className="row nav-links" style={{ gap: "8px", flexWrap: "wrap" }}>
              <Link href="/dashboard">Dashboard</Link>
              <Link href="/leads">Leads</Link>
              <Link href="/integrations">Integrations</Link>
              <Link href="/appointments">Appointments</Link>
              <Link href="/reports">Reports</Link>
              <Link href="/login">Login</Link>
            </nav>
          </div>
        </header>

        {children}

        <footer className="site-footer">
          <div className="container row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
            <p className="small">© {new Date().getFullYear()} RealEstateAI</p>
            <div className="row" style={{ gap: "12px" }}>
              <Link href="/terms" className="small">Terms of Use</Link>
              <Link href="/privacy" className="small">Privacy Policy</Link>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
