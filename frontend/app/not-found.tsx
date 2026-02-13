import Link from "next/link";

export default function NotFound() {
  return (
    <main className="container">
      <section className="card">
        <h1>Page Not Found</h1>
        <p className="small">The page you requested does not exist. Use the links below to continue.</p>
        <div className="row" style={{ gap: "10px", flexWrap: "wrap" }}>
          <Link href="/"><button>Home</button></Link>
          <Link href="/dashboard"><button>Dashboard</button></Link>
          <Link href="/login"><button>Login</button></Link>
        </div>
      </section>
    </main>
  );
}
