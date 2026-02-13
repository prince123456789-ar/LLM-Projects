"use client";

import { useEffect, useState } from "react";
import { fetchDashboard } from "@/lib/api";

export default function DashboardPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token") || "";
    if (!token) {
      setError("Login first");
      return;
    }

    fetchDashboard(token)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"));
  }, []);

  return (
    <main className="container grid">
      <section className="card">
        <h2>Dashboard</h2>
        {error ? <p className="small">{error}</p> : null}
        {data ? (
          <div className="grid">
            <div className="card"><strong>Total Leads:</strong> {String(data.total_leads)}</div>
            <div className="card"><strong>Converted Leads:</strong> {String(data.converted_leads)}</div>
            <div className="card"><strong>Conversion Rate:</strong> {String(data.conversion_rate)}%</div>
            <div className="card"><strong>Average Score:</strong> {String(data.avg_lead_score)}</div>
            <div className="card">
              <strong>By Channel</strong>
              <pre>{JSON.stringify(data.by_channel, null, 2)}</pre>
            </div>
            <div className="card">
              <strong>By Agent</strong>
              <pre>{JSON.stringify(data.by_agent, null, 2)}</pre>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
