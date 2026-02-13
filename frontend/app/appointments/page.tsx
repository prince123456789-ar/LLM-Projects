"use client";

import { useEffect, useState } from "react";
import { createAppointment, fetchAppointmentSuggestions } from "@/lib/api";

export default function AppointmentsPage() {
  const [suggestions, setSuggestions] = useState<{ start_at: string; end_at: string }[]>([]);
  const [payload, setPayload] = useState({
    lead_id: 1,
    agent_id: 3,
    start_at: "",
    end_at: "",
    timezone: "UTC",
    location: "Office"
  });
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token") || "";
    if (!token) return;
    fetchAppointmentSuggestions(token)
      .then((data) => {
        setSuggestions(data);
        if (data.length > 0) {
          setPayload((p) => ({ ...p, start_at: data[0].start_at, end_at: data[0].end_at }));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load suggestions"));
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = localStorage.getItem("token") || "";
    if (!token) {
      setError("Login first");
      return;
    }

    try {
      const created = await createAppointment(token, payload);
      setMessage(`Appointment created: #${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create appointment");
    }
  }

  return (
    <main className="container grid">
      <section className="card">
        <h2>Appointment Scheduling</h2>
        <p className="small">Default agent_id=3 matches seeded `agent@agency.com` in this starter.</p>
        <form className="grid" onSubmit={onCreate}>
          <input type="number" value={payload.lead_id} onChange={(e) => setPayload({ ...payload, lead_id: Number(e.target.value) })} placeholder="Lead ID" />
          <input type="number" value={payload.agent_id} onChange={(e) => setPayload({ ...payload, agent_id: Number(e.target.value) })} placeholder="Agent ID" />
          <select
            value={`${payload.start_at}|${payload.end_at}`}
            onChange={(e) => {
              const [start_at, end_at] = e.target.value.split("|");
              setPayload({ ...payload, start_at, end_at });
            }}
          >
            {suggestions.map((s, idx) => (
              <option key={idx} value={`${s.start_at}|${s.end_at}`}>
                {s.start_at} -> {s.end_at}
              </option>
            ))}
          </select>
          <input value={payload.timezone} onChange={(e) => setPayload({ ...payload, timezone: e.target.value })} placeholder="Timezone" />
          <input value={payload.location} onChange={(e) => setPayload({ ...payload, location: e.target.value })} placeholder="Location" />
          <button type="submit">Create Appointment</button>
        </form>
        {message ? <p className="small">{message}</p> : null}
        {error ? <p className="small">{error}</p> : null}
      </section>
    </main>
  );
}
