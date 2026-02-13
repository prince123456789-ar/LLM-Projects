"use client";

import { useEffect, useState } from "react";
import { createScheduledReport, downloadReport, listScheduledReports, sendScheduledReportNow } from "@/lib/api";

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const [frequency, setFrequency] = useState("weekly");
  const [recipientEmail, setRecipientEmail] = useState("manager@agency.com");
  const [scheduled, setScheduled] = useState<Record<string, unknown>[]>([]);

  async function loadScheduled() {
    const token = localStorage.getItem("token") || "";
    if (!token) return;
    const items = await listScheduledReports(token);
    setScheduled(items);
  }

  useEffect(() => {
    loadScheduled().catch(() => undefined);
  }, []);

  async function onDownload(kind: "csv" | "pdf") {
    const token = localStorage.getItem("token") || "";
    if (!token) {
      alert("Login first");
      return;
    }

    try {
      const blob = await downloadReport(token, kind);
      saveBlob(blob, kind === "csv" ? "leads.csv" : "analytics.pdf");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Download failed");
    }
  }

  async function onCreateSchedule(e: React.FormEvent) {
    e.preventDefault();
    const token = localStorage.getItem("token") || "";
    if (!token) {
      alert("Login first");
      return;
    }

    try {
      await createScheduledReport(token, {
        frequency,
        recipient_email: recipientEmail,
        report_type: "analytics"
      });
      await loadScheduled();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Schedule create failed");
    }
  }

  async function onSendNow(reportId: number) {
    const token = localStorage.getItem("token") || "";
    if (!token) {
      alert("Login first");
      return;
    }

    try {
      await sendScheduledReportNow(token, reportId);
      alert("Scheduled report queued");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Queue failed");
    }
  }

  return (
    <main className="container main-shell">
      <section className="card">
        <h2>Reports Export</h2>
        <p className="small">Protected downloads for managers/admins.</p>
        <div className="grid">
          <button onClick={() => onDownload("csv")}>Download Leads CSV</button>
          <button onClick={() => onDownload("pdf")}>Download Analytics PDF</button>
        </div>
      </section>

      <section className="card">
        <h2>Scheduled Reports</h2>
        <form className="grid" onSubmit={onCreateSchedule}>
          <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
          <input value={recipientEmail} onChange={(e) => setRecipientEmail(e.target.value)} placeholder="Recipient Email" />
          <button type="submit">Create Schedule</button>
        </form>

        <div className="grid">
          {scheduled.map((item, idx) => (
            <div className="card" key={idx}>
              <pre>{JSON.stringify(item, null, 2)}</pre>
              <button onClick={() => onSendNow(Number(item.id))}>Send Now</button>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
