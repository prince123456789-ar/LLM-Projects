const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type Lead = {
  id: number;
  full_name: string;
  email?: string;
  phone?: string;
  channel: string;
  status: string;
  score: number;
  property_type?: string;
  location?: string;
  budget?: number;
  timeline?: string;
  assigned_agent_id?: number;
  created_at: string;
};

export type LoginTokens = {
  access_token: string;
  refresh_token: string;
};

export function getDeviceId(): string {
  const key = "device_id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

function authHeader(token: string) {
  return {
    Authorization: `Bearer ${token}`,
    "x-device-id": getDeviceId()
  };
}

export async function login(email: string, password: string): Promise<LoginTokens> {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);

  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "x-device-id": getDeviceId()
    },
    body
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  return { access_token: data.access_token, refresh_token: data.refresh_token };
}

export async function refreshAccessToken(refreshToken: string): Promise<LoginTokens> {
  const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-device-id": getDeviceId()
    },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  if (!res.ok) throw new Error("Session expired");
  const data = await res.json();
  return { access_token: data.access_token, refresh_token: data.refresh_token };
}

async function withAuthRetry(input: string, init: RequestInit = {}) {
  let access = localStorage.getItem("token") || "";
  let refresh = localStorage.getItem("refresh_token") || "";

  const run = async (token: string) => {
    const headers = {
      ...(init.headers || {}),
      ...authHeader(token)
    } as Record<string, string>;

    return fetch(input, { ...init, headers });
  };

  let res = await run(access);
  if (res.status === 401 && refresh) {
    const tokens = await refreshAccessToken(refresh);
    localStorage.setItem("token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    access = tokens.access_token;
    refresh = tokens.refresh_token;
    res = await run(access);
  }

  return res;
}

export async function fetchLeads(token: string): Promise<Lead[]> {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/leads`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load leads");
  return res.json();
}

export async function createLead(token: string, payload: Record<string, unknown>): Promise<Lead> {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/leads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Failed to create lead");
  return res.json();
}

export async function fetchDashboard(token: string): Promise<Record<string, unknown>> {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/analytics/dashboard`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load dashboard");
  return res.json();
}

export async function fetchIntegrations(token: string): Promise<Record<string, unknown>[]> {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/integrations/channels`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load integrations");
  return res.json();
}

export async function saveIntegration(token: string, payload: Record<string, unknown>) {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/integrations/channels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Failed to save integration");
  return res.json();
}

export async function fetchAppointmentSuggestions(token: string) {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/appointments/suggestions`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load suggestions");
  return res.json();
}

export async function createAppointment(token: string, payload: Record<string, unknown>) {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/appointments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Failed to create appointment");
  return res.json();
}

export async function downloadReport(token: string, kind: "csv" | "pdf") {
  localStorage.setItem("token", token);
  const endpoint = kind === "csv" ? "leads.csv" : "analytics.pdf";
  const res = await withAuthRetry(`${API_BASE}/api/v1/reports/${endpoint}`);
  if (!res.ok) throw new Error(`Failed to download ${kind.toUpperCase()} report`);
  return res.blob();
}

export async function createScheduledReport(token: string, payload: Record<string, unknown>) {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/reports/scheduled`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Failed to create scheduled report");
  return res.json();
}

export async function listScheduledReports(token: string) {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/reports/scheduled`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to list scheduled reports");
  return res.json();
}

export async function sendScheduledReportNow(token: string, reportId: number) {
  localStorage.setItem("token", token);
  const res = await withAuthRetry(`${API_BASE}/api/v1/reports/scheduled/${reportId}/send-now`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to queue scheduled report");
  return res.json();
}
