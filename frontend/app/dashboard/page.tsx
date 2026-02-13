"use client";
import { useEffect, useState } from "react";
import { fetchDashboard } from "@/lib/api";

export default function DashboardPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { const token = localStorage.getItem("token") || ""; if (!token) return setError("Login first"); fetchDashboard(token).then(setData).catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard")); }, []);

  return <main className="container main-shell"><section className="card"><h1>Agency Performance Dashboard</h1><p className="small">Real-time visibility into lead flow, conversion, and assignment outcomes.</p></section>{error ? <section className="card"><p className="small">{error}</p></section> : null}{data ? <section className="grid metric-grid"><div className="card metric"><h3>Total Leads</h3><p>{String(data.total_leads)}</p></div><div className="card metric"><h3>Converted</h3><p>{String(data.converted_leads)}</p></div><div className="card metric"><h3>Conversion Rate</h3><p>{String(data.conversion_rate)}%</p></div><div className="card metric"><h3>Avg Score</h3><p>{String(data.avg_lead_score)}</p></div><div className="card"><h3>By Channel</h3><pre>{JSON.stringify(data.by_channel, null, 2)}</pre></div><div className="card"><h3>By Agent</h3><pre>{JSON.stringify(data.by_agent, null, 2)}</pre></div></section> : null}</main>;
}