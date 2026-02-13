"use client";

import { useEffect, useState } from "react";
import { createLead, fetchLeads, Lead } from "@/lib/api";

const defaultPayload = {
  full_name: "",
  email: "",
  phone: "",
  channel: "website_chat",
  raw_message: ""
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [payload, setPayload] = useState(defaultPayload);
  const [error, setError] = useState("");

  async function loadLeads() {
    const token = localStorage.getItem("token") || "";
    if (!token) return;
    try {
      const data = await fetchLeads(token);
      setLeads(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leads");
    }
  }

  useEffect(() => {
    loadLeads();
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = localStorage.getItem("token") || "";
    if (!token) {
      setError("Login first");
      return;
    }

    try {
      await createLead(token, payload);
      setPayload(defaultPayload);
      await loadLeads();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  return (
    <main className="container main-shell">
      <section className="card">
        <h2>New Lead</h2>
        <form className="grid" onSubmit={onCreate}>
          <input placeholder="Full name" value={payload.full_name} onChange={(e) => setPayload({ ...payload, full_name: e.target.value })} />
          <input placeholder="Email" value={payload.email} onChange={(e) => setPayload({ ...payload, email: e.target.value })} />
          <input placeholder="Phone" value={payload.phone} onChange={(e) => setPayload({ ...payload, phone: e.target.value })} />
          <select value={payload.channel} onChange={(e) => setPayload({ ...payload, channel: e.target.value })}>
            <option value="website_chat">Website Chat</option>
            <option value="email">Email</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
          </select>
          <textarea placeholder="Lead message" value={payload.raw_message} onChange={(e) => setPayload({ ...payload, raw_message: e.target.value })} />
          <button type="submit">Create Lead</button>
        </form>
        {error ? <p className="small">{error}</p> : null}
      </section>

      <section className="card">
        <h2>Lead List</h2>
        <div className="grid">
          {leads.map((lead) => (
            <div key={lead.id} className="card">
              <strong>{lead.full_name}</strong>
              <p className="small">{lead.channel} | {lead.status} | Score: {lead.score}</p>
              <p className="small">{lead.location || "No location"} | Budget: {lead.budget || "N/A"}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
