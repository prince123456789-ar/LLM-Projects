import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container grid">
      <section className="card hero">
        <h1>Real Estate AI SaaS</h1>
        <p className="small">
          Automate lead intake across channels, score and route leads with AI, schedule appointments, and track conversion in one place.
        </p>

        <div className="row" style={{ gap: "10px", flexWrap: "wrap" }}>
          <Link href="/login"><button>Get Started</button></Link>
          <Link href="/dashboard"><button>Open Dashboard</button></Link>
        </div>
      </section>

      <section className="grid cards-3">
        <div className="card">
          <h3>Lead Intelligence</h3>
          <p className="small">Capture, dedupe, score, and assign leads automatically.</p>
          <Link href="/leads" className="small">Open Leads →</Link>
        </div>
        <div className="card">
          <h3>Integrations</h3>
          <p className="small">Connect WhatsApp, Instagram, Facebook, email, and calendars.</p>
          <Link href="/integrations" className="small">Open Integrations →</Link>
        </div>
        <div className="card">
          <h3>Operations</h3>
          <p className="small">Appointments, reports, and analytics for teams and managers.</p>
          <Link href="/reports" className="small">Open Reports →</Link>
        </div>
      </section>
    </main>
  );
}
