import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container grid">
      <section className="card">
        <h1>Real Estate AI SaaS</h1>
        <p className="small">Lead management, NLP qualification, assignment automation, scheduling, integrations, and reporting.</p>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <Link href="/login"><button>Login</button></Link>
          <Link href="/leads"><button>Leads</button></Link>
          <Link href="/dashboard"><button>Dashboard</button></Link>
          <Link href="/integrations"><button>Integrations</button></Link>
          <Link href="/appointments"><button>Appointments</button></Link>
          <Link href="/reports"><button>Reports</button></Link>
        </div>
      </section>
    </main>
  );
}
