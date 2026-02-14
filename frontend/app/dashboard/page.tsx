"use client";
import { useEffect, useState } from "react";
import { fetchDashboard } from "@/lib/api";
import styles from "./dashboard.module.css";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://cdc2-154-161-30-60.ngrok-free.app";

const EMBED_SCRIPT_URL = `${API_BASE}/embed.js?key=rea_pub_34ff2da6116aa7f18a4c8dd1701575420d413de2581c5c21`;

export default function DashboardPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token") || "";
    if (!token) return setError("Login first");
    fetchDashboard(token)
      .then(setData)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load dashboard")
      );
  }, []);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(EMBED_SCRIPT_URL);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <main className={styles.container}>
      <section className={styles.header}>
        <h1>Agency Performance Dashboard</h1>
        <p className={styles.subtitle}>
          Real-time visibility into lead flow, conversion, and assignment outcomes.
        </p>
      </section>

      {error ? (
        <section className={styles.errorCard}>
          <p className={styles.errorText}>{error}</p>
        </section>
      ) : null}

      {data ? (
        <>
          <section className={styles.metricsGrid}>
            <div className={styles.metricCard}>
              <h3>Total Leads</h3>
              <p className={styles.metricValue}>{String(data.total_leads)}</p>
            </div>
            <div className={styles.metricCard}>
              <h3>Converted</h3>
              <p className={styles.metricValue}>
                {String(data.converted_leads)}
              </p>
            </div>
            <div className={styles.metricCard}>
              <h3>Conversion Rate</h3>
              <p className={styles.metricValue}>
                {String(data.conversion_rate)}%
              </p>
            </div>
            <div className={styles.metricCard}>
              <h3>Avg Score</h3>
              <p className={styles.metricValue}>
                {String(data.avg_lead_score)}
              </p>
            </div>
          </section>

          <section className={styles.dataGrid}>
            <div className={styles.dataCard}>
              <h3>By Channel</h3>
              <div className={styles.dataContent}>
                <pre>{JSON.stringify(data.by_channel, null, 2)}</pre>
              </div>
            </div>
            <div className={styles.dataCard}>
              <h3>By Agent</h3>
              <div className={styles.dataContent}>
                <pre>{JSON.stringify(data.by_agent, null, 2)}</pre>
              </div>
            </div>
          </section>
        </>
      ) : null}

      <section className={styles.embedCard}>
        <h2>Embed Script</h2>
        <p className={styles.embedDescription}>
          Copy the script below to embed this dashboard on your website:
        </p>
        <div className={styles.embedBox}>
          <div className={styles.embedUrl}>
            <code className={styles.codeText}>{EMBED_SCRIPT_URL}</code>
            <button
              onClick={copyToClipboard}
              className={styles.copyButton}
              title="Copy embed script"
            >
              {copied ? "✓ Copied" : "Copy"}
            </button>
          </div>
        </div>
        <div className={styles.scriptPreview}>
          <p className={styles.scriptLabel}>Script Tag:</p>
          <div className={styles.codeBlock}>
            <code>
              &lt;script src=&quot;{EMBED_SCRIPT_URL}&quot; async&gt;&lt;/script&gt;
            </code>
          </div>
        </div>
      </section>
    </main>
  );
}