"use client";

import { useEffect, useState } from "react";
import { fetchIntegrations, saveIntegration } from "@/lib/api";

const metaWhatsappTemplate = JSON.stringify(
  {
    meta_api_version: "v21.0",
    whatsapp_phone_number_id: "YOUR_PHONE_NUMBER_ID",
    meta_verify_token: "YOUR_VERIFY_TOKEN",
    meta_app_secret: "YOUR_APP_SECRET"
  },
  null,
  2
);

const emptyPayload = {
  channel: "whatsapp",
  provider_name: "meta",
  webhook_url: "",
  api_key_ref: "",
  metadata_json: metaWhatsappTemplate
};

export default function IntegrationsPage() {
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [payload, setPayload] = useState(emptyPayload);
  const [error, setError] = useState("");

  async function load() {
    const token = localStorage.getItem("token") || "";
    if (!token) return;
    try {
      setItems(await fetchIntegrations(token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrations");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    const token = localStorage.getItem("token") || "";
    if (!token) {
      setError("Login first");
      return;
    }

    try {
      await saveIntegration(token, payload);
      setPayload(emptyPayload);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save integration");
    }
  }

  return (
    <main className="container grid">
      <section className="card">
        <h2>Channel Integrations</h2>
        <p className="small">
          For Meta channels set `provider_name` to `meta`, put access token in `api_key_ref`, and use metadata JSON template for webhook verification/signature.
        </p>
        <form className="grid" onSubmit={onSave}>
          <select value={payload.channel} onChange={(e) => setPayload({ ...payload, channel: e.target.value })}>
            <option value="whatsapp">WhatsApp</option>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
            <option value="email">Email</option>
            <option value="website_chat">Website Chat</option>
          </select>
          <input placeholder="Provider name" value={payload.provider_name} onChange={(e) => setPayload({ ...payload, provider_name: e.target.value })} />
          <input placeholder="Webhook URL (only for non-Meta providers)" value={payload.webhook_url} onChange={(e) => setPayload({ ...payload, webhook_url: e.target.value })} />
          <input placeholder="API key / token" value={payload.api_key_ref} onChange={(e) => setPayload({ ...payload, api_key_ref: e.target.value })} />
          <textarea placeholder="Metadata JSON" value={payload.metadata_json} onChange={(e) => setPayload({ ...payload, metadata_json: e.target.value })} />
          <button type="submit">Save Integration</button>
        </form>
      </section>

      <section className="card">
        <h3>Configured Integrations</h3>
        {items.map((item, idx) => (
          <pre key={idx} className="card">{JSON.stringify(item, null, 2)}</pre>
        ))}
        {error ? <p className="small">{error}</p> : null}
      </section>
    </main>
  );
}
