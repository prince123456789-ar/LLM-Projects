import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container main-shell">
      <section className="card hero"><h1>Close More Deals With AI-Powered Real Estate Operations</h1><p className="small">Capture leads from WhatsApp, Instagram, Facebook, and web chat. Score intent, auto-route to agents, and track revenue pipeline in one command center.</p><div className="row" style={{ flexWrap: "wrap" }}><Link href="/login"><button>Start Free Setup</button></Link><Link href="/pricing"><button className="secondary">View Pricing</button></Link><Link href="/dashboard"><button className="secondary">See Dashboard</button></Link></div></section>
      <section className="grid cards-3"><article className="card"><h3>Lead Intelligence</h3><p className="small">NLP extraction, duplicate merge, lead scoring, and assignment automation.</p><Link href="/leads" className="small">Open Leads</Link></article><article className="card"><h3>Omnichannel Integrations</h3><p className="small">Meta channels, email, and webhook ingestion with security verification.</p><Link href="/integrations" className="small">Open Integrations</Link></article><article className="card"><h3>Team Execution</h3><p className="small">Appointments, reports, and conversion visibility for managers and agents.</p><Link href="/reports" className="small">Open Reports</Link></article></section>
    </main>
  );
}