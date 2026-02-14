function getDeviceId() {
  const k = "device_id";
  let v = localStorage.getItem(k);
  if (!v) {
    v = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2);
    localStorage.setItem(k, v);
  }
  return v;
}

async function login(email, password) {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "x-device-id": getDeviceId() },
    body
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  return data;
}

async function getMe() {
  const res = await apiFetch("/api/v1/auth/me", { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

async function refreshTokens() {
  const refresh = localStorage.getItem("refresh_token") || "";
  if (!refresh) throw new Error("No refresh token");
  const res = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-device-id": getDeviceId() },
    body: JSON.stringify({ refresh_token: refresh })
  });
  if (!res.ok) throw new Error("Session expired");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  return data;
}

async function apiFetch(path, init) {
  const token = localStorage.getItem("token") || "";
  const headers = new Headers((init && init.headers) || {});
  headers.set("x-device-id", getDeviceId());
  if (token) headers.set("Authorization", "Bearer " + token);
  const res = await fetch(path, { ...(init || {}), headers });
  if (res.status === 401) {
    await refreshTokens();
    const token2 = localStorage.getItem("token") || "";
    const headers2 = new Headers((init && init.headers) || {});
    headers2.set("x-device-id", getDeviceId());
    if (token2) headers2.set("Authorization", "Bearer " + token2);
    return fetch(path, { ...(init || {}), headers: headers2 });
  }
  return res;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function onLoginPage() {
  const form = document.getElementById("loginForm");
  const msg = document.getElementById("loginMsg");
  const logoutBtn = document.getElementById("logoutBtn");
  if (!form) return;

  // If there's no session, don't show logout.
  try {
    const hasSession = !!(localStorage.getItem("token") || localStorage.getItem("refresh_token"));
    if (logoutBtn) logoutBtn.style.display = hasSession ? "inline-flex" : "none";
  } catch (_) {}

  // OAuth callback token handoff (URL fragment, never sent to server).
  try {
    if (window.location.hash && window.location.hash.includes("access_token=")) {
      const h = window.location.hash.replace(/^#/, "");
      const params = new URLSearchParams(h);
      const access = params.get("access_token");
      const refresh = params.get("refresh_token");
      const device = params.get("device_id");
      const next = params.get("next") || "/app/dashboard";
      if (access && refresh) {
        localStorage.setItem("token", access);
        localStorage.setItem("refresh_token", refresh);
      }
      if (device) localStorage.setItem("device_id", device);
      window.location.hash = "";
      window.location.href = next;
      return;
    }
  } catch (_) {}

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.textContent = "Signing in...";
    try {
      const email = document.getElementById("email").value;
      const password = document.getElementById("password").value;
      await login(email, password);
      const me = await getMe();
      msg.textContent = "Signed in. Redirecting...";
      if (me && me.role === "admin") window.location.href = "/app/admin";
      else window.location.href = "/app/dashboard";
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Sign in failed";
    }
  });

  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem("token");
      localStorage.removeItem("refresh_token");
      msg.textContent = "Logged out.";
      logoutBtn.style.display = "none";
    });
  }
}

async function onDashboardPage() {
  try {
    const res = await apiFetch("/api/v1/analytics/dashboard", { cache: "no-store" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || ("Failed to load dashboard (" + res.status + ")"));
    }
    const data = await res.json();
    setText("mTotal", String(data.total_leads ?? "-"));
    setText("mResp", String(data.avg_response_time ?? "-"));
    setText("mConv", String(data.conversion_rate ?? "-"));
    setText("dashMsg", "Live metrics loaded from API.");
  } catch (err) {
    setText("dashMsg", (err && err.message) ? err.message : "Login required (or API not ready).");
  }
}

function renderLeads(rows) {
  const tbody = document.querySelector("#leadTable tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  rows.forEach((l) => {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td>" + l.id + "</td><td>" + (l.full_name || "") + "</td><td>" + (l.channel || "") + "</td><td>" + (l.score ?? "") + "</td><td>" + (l.status || "") + "</td>";
    tbody.appendChild(tr);
  });
}

async function loadLeads() {
  const res = await apiFetch("/api/v1/leads", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load leads");
  return res.json();
}

function onLeadsPage() {
  const msg = document.getElementById("leadMsg");
  const refresh = document.getElementById("refreshLeads");
  const form = document.getElementById("leadForm");

  async function refreshNow() {
    msg.textContent = "Loading...";
    try {
      const leads = await loadLeads();
      renderLeads(leads);
      msg.textContent = "Loaded " + leads.length + " leads.";
    } catch (err) {
      msg.textContent = "Login required (or API not ready).";
    }
  }

  if (refresh) refresh.addEventListener("click", refreshNow);
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      msg.textContent = "Creating...";
      try {
        const payload = {
          full_name: document.getElementById("lName").value,
          email: document.getElementById("lEmail").value || null,
          phone: document.getElementById("lPhone").value || null,
          channel: document.getElementById("lChannel").value || "website_chat",
          location: document.getElementById("lLocation").value || null,
          property_type: document.getElementById("lPropertyType").value || null,
          budget: document.getElementById("lBudget").value ? Number(document.getElementById("lBudget").value) : null,
          timeline: document.getElementById("lTimeline").value || null
        };
        const res = await apiFetch("/api/v1/leads", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "Failed to create lead");
        }
        msg.textContent = "Created lead.";
        await refreshNow();
      } catch (err) {
        msg.textContent = (err && err.message) ? err.message : "Create failed";
      }
    });
  }

  refreshNow();
}

async function onIntegrationsPage() {
  const out = document.getElementById("integrationsList");
  const btn = document.getElementById("refreshIntegrations");
  async function load() {
    out.textContent = "Loading...";
    try {
      const res = await apiFetch("/api/v1/integrations/channels", { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to load integrations");
      const data = await res.json();
      out.textContent = JSON.stringify(data, null, 2);
      out.style.whiteSpace = "pre-wrap";
      out.style.fontFamily = "ui-monospace, Menlo, Consolas, monospace";
    } catch (err) {
      out.textContent = "Login required (or API not ready).";
    }
  }
  if (btn) btn.addEventListener("click", load);
  load();
}

async function onAppointmentsPage() {
  const msg = document.getElementById("apptMsg");
  const slot = document.getElementById("aSlot");
  const loadBtn = document.getElementById("loadSlots");
  const form = document.getElementById("apptForm");

  async function loadSlots() {
    msg.textContent = "Loading slots...";
    try {
      const res = await apiFetch("/api/v1/appointments/suggestions", { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to load suggestions");
      const data = await res.json();
      slot.innerHTML = "";
      data.forEach((s) => {
        const o = document.createElement("option");
        o.value = s.start_at + "|" + s.end_at;
        o.textContent = s.start_at + " -> " + s.end_at;
        slot.appendChild(o);
      });
      msg.textContent = "Loaded " + data.length + " slots.";
    } catch (err) {
      msg.textContent = "Login required (or API not ready).";
    }
  }

  if (loadBtn) loadBtn.addEventListener("click", loadSlots);
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      msg.textContent = "Creating appointment...";
      try {
        const parts = (slot.value || "|").split("|");
        const payload = {
          lead_id: Number(document.getElementById("aLeadId").value || "1"),
          agent_id: Number(document.getElementById("aAgentId").value || "3"),
          start_at: parts[0] || "",
          end_at: parts[1] || "",
          timezone: document.getElementById("aTimezone").value || "UTC",
          location: document.getElementById("aLocation").value || "Office"
        };
        const res = await apiFetch("/api/v1/appointments", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Failed to create appointment");
        msg.textContent = "Created.";
      } catch (err) {
        msg.textContent = (err && err.message) ? err.message : "Create failed";
      }
    });
  }

  loadSlots();
}

function drawLineChart(canvas, series) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const w = canvas.width, h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  const pad = 18;
  const innerW = w - pad * 2;
  const innerH = h - pad * 2;

  const vals = series.map((p) => p.value);
  const minV = Math.min.apply(null, vals.concat([0]));
  const maxV = Math.max.apply(null, vals.concat([1]));

  function x(i) {
    const t = series.length <= 1 ? 0 : i / (series.length - 1);
    return pad + t * innerW;
  }
  function y(v) {
    const t = (v - minV) / (maxV - minV || 1);
    return pad + (1 - t) * innerH;
  }

  // Grid
  ctx.strokeStyle = "rgba(255,255,255,.10)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const yy = pad + (innerH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(pad, yy);
    ctx.lineTo(pad + innerW, yy);
    ctx.stroke();
  }

  // Line
  ctx.strokeStyle = "rgba(88,240,194,.95)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  series.forEach((p, i) => {
    const xx = x(i);
    const yy = y(p.value);
    if (i === 0) ctx.moveTo(xx, yy);
    else ctx.lineTo(xx, yy);
  });
  ctx.stroke();

  // Fill
  const grad = ctx.createLinearGradient(0, pad, 0, pad + innerH);
  grad.addColorStop(0, "rgba(88,240,194,.20)");
  grad.addColorStop(1, "rgba(88,240,194,0)");
  ctx.fillStyle = grad;
  ctx.lineTo(pad + innerW, pad + innerH);
  ctx.lineTo(pad, pad + innerH);
  ctx.closePath();
  ctx.fill();

  // Labels
  ctx.fillStyle = "rgba(234,240,255,.70)";
  ctx.font = "12px ui-monospace, Menlo, Consolas, monospace";
  ctx.fillText(String(maxV.toFixed(0)), pad, pad + 10);
  ctx.fillText(String(minV.toFixed(0)), pad, pad + innerH);
}

async function onDashboardChart() {
  const msg = document.getElementById("chartMsg");
  const btn = document.getElementById("refreshChart");
  const canvas = document.getElementById("kpiChart");

  async function load() {
    msg.textContent = "Loading...";
    try {
      const mRes = await apiFetch("/api/v1/analytics/dashboard", { cache: "no-store" });
      if (!mRes.ok) {
        const d = await mRes.json().catch(() => ({}));
        throw new Error(d.detail || ("Failed to load dashboard (" + mRes.status + ")"));
      }
      const m = await mRes.json();
      setText("mTotal", String(m.total_leads ?? "-"));
      setText("mScore", String(m.avg_lead_score ?? "-"));
      setText("mConv", String(m.conversion_rate ?? "-") + "%");
      setText("mMrr", "$" + String(m.mrr_usd ?? 0));
      setText("mProfit", "$" + String(m.profit_usd ?? 0));
      setText("mLoss", "$" + String(m.losses_usd ?? 0));

      const res = await apiFetch("/api/v1/analytics/timeseries?days=30", { cache: "no-store" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || ("Failed to load chart (" + res.status + ")"));
      }
      const data = await res.json();
      const series = (data || []).map((p) => ({ label: p.day, value: Number(p.profit_usd || 0) }));
      drawLineChart(canvas, series.length ? series : [{ label: "0", value: 0 }]);
      msg.textContent = "Updated.";
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Login required (or API not ready).";
    }
  }

  if (btn) btn.addEventListener("click", load);
  load();
}

function renderAudit(rows) {
  const tbody = document.querySelector("#auditTable tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  rows.forEach((a) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + (a.created_at || "") + "</td>" +
      "<td>" + (a.action || "") + "</td>" +
      "<td>" + (a.resource || "") + "</td>" +
      "<td>" + (a.user_id == null ? "" : String(a.user_id)) + "</td>" +
      "<td>" + (a.details || "") + "</td>";
    tbody.appendChild(tr);
  });
}

async function onAuditPage() {
  const msg = document.getElementById("auditMsg");
  const btn = document.getElementById("refreshAudit");

  async function load() {
    msg.textContent = "Loading...";
    try {
      const res = await apiFetch("/api/v1/audit?limit=100", { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to load audit log");
      const data = await res.json();
      renderAudit(data || []);
      msg.textContent = "Loaded " + (data ? data.length : 0) + " events.";
    } catch (err) {
      msg.textContent = "Login required (admin/manager) or API not ready.";
    }
  }

  if (btn) btn.addEventListener("click", load);
  load();
}

async function onRegisterPage() {
  const form = document.getElementById("registerForm");
  const msg = document.getElementById("registerMsg");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.textContent = "Registering...";
    try {
      const payload = {
        full_name: document.getElementById("rName").value,
        email: document.getElementById("rEmail").value,
        password: document.getElementById("rPassword").value,
        role: document.getElementById("rRole").value
      };
      const res = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Registration failed");
      msg.textContent = "Registered. You can now sign in.";
      setTimeout(() => { window.location.href = "/app/login"; }, 800);
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Registration failed";
    }
  });
}

async function onBillingPage() {
  const msg = document.getElementById("billingMsg");
  const statusEl = document.getElementById("billingStatus");
  const planSelect = document.getElementById("planSelect");
  const checkoutBtn = document.getElementById("startCheckout");
  const portalBtn = document.getElementById("openPortal");
  const refreshBtn = document.getElementById("refreshBilling");

  async function refreshStatus() {
    msg.textContent = "";
    statusEl.textContent = "Loading...";
    try {
      const res = await apiFetch("/api/v1/billing/status", { cache: "no-store" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to load billing status");
      }
      const data = await res.json();
      statusEl.textContent = `Status: ${data.status} | Plan: ${data.plan} | Customer linked: ${data.has_customer ? "yes" : "no"}`;
    } catch (err) {
      statusEl.textContent = "";
      msg.textContent = (err && err.message) ? err.message : "Billing status unavailable";
    }
  }

  async function startCheckout() {
    msg.textContent = "Creating checkout session...";
    try {
      const plan = planSelect && planSelect.value ? planSelect.value : "agency";
      const res = await apiFetch(`/api/v1/billing/checkout?plan=${encodeURIComponent(plan)}`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Checkout failed");
      if (!data.checkout_url) throw new Error("No checkout URL returned");
      window.location.href = data.checkout_url;
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Checkout failed";
    }
  }

  async function openPortal() {
    msg.textContent = "Opening customer portal...";
    try {
      const res = await apiFetch("/api/v1/billing/portal", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Portal unavailable");
      if (!data.portal_url) throw new Error("No portal URL returned");
      window.location.href = data.portal_url;
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Portal unavailable";
    }
  }

  async function setAutoRenew(enabled) {
    msg.textContent = "Saving...";
    try {
      const res = await apiFetch(`/api/v1/billing/auto-renew?enabled=${enabled ? "true" : "false"}`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to update auto-renew");
      msg.textContent = "Saved.";
      await refreshStatus();
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Failed to update auto-renew";
    }
  }

  if (checkoutBtn) checkoutBtn.addEventListener("click", startCheckout);
  if (portalBtn) portalBtn.addEventListener("click", openPortal);
  if (refreshBtn) refreshBtn.addEventListener("click", refreshStatus);
  refreshStatus();
}

async function onForgotPasswordPage() {
  const form = document.getElementById("forgotForm");
  const msg = document.getElementById("forgotMsg");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.textContent = "Sending...";
    try {
      const payload = { email: document.getElementById("fEmail").value };
      const res = await fetch("/api/v1/password/forgot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Request failed");
      msg.textContent = "If the email exists, a reset link has been sent.";
    } catch (err) {
      msg.textContent = "If the email exists, a reset link has been sent.";
    }
  });
}

async function onResetPasswordPage() {
  const form = document.getElementById("resetForm");
  const msg = document.getElementById("resetMsg");
  const tokenInput = document.getElementById("rToken");
  if (!form) return;

  try {
    const url = new URL(window.location.href);
    const t = url.searchParams.get("token");
    if (t && tokenInput) tokenInput.value = t;
  } catch (_) {}

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.textContent = "Updating...";
    try {
      const payload = {
        token: (document.getElementById("rToken").value || "").trim(),
        new_password: document.getElementById("rNewPassword").value
      };
      const res = await fetch("/api/v1/password/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Reset failed");
      msg.textContent = "Password updated. You can sign in now.";
      setTimeout(() => { window.location.href = "/app/login"; }, 900);
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Reset failed";
    }
  });
}

function renderUsers(rows) {
  const tbody = document.querySelector("#usersTable tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  rows.forEach((u) => {
    const tr = document.createElement("tr");
    const locked = u.locked_until ? "yes" : "";
    const active = u.is_active ? "yes" : "no";
    tr.innerHTML =
      "<td>" + u.id + "</td>" +
      "<td>" + (u.email || "") + "</td>" +
      "<td>" + (u.full_name || "") + "</td>" +
      "<td>" + (u.role || "") + "</td>" +
      "<td>" + active + "</td>" +
      "<td>" + locked + "</td>" +
      "<td><button class=\"btn\" data-disable=\"" + u.id + "\">Disable</button></td>";
    tbody.appendChild(tr);
  });
}

async function onAdminPage() {
  const msg = document.getElementById("adminMsg");
  const btn = document.getElementById("refreshUsers");

  async function load() {
    msg.textContent = "Loading...";
    try {
      const res = await apiFetch("/api/v1/admin/users", { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed to load users");
      renderUsers(data || []);
      msg.textContent = "Loaded " + (data ? data.length : 0) + " users.";
    } catch (err) {
      msg.textContent = (err && err.message) ? err.message : "Admin access required";
    }
  }

  document.addEventListener("click", async (e) => {
    const t = e.target;
    if (t && t.dataset && t.dataset.disable) {
      msg.textContent = "Disabling user...";
      try {
        const res = await apiFetch(`/api/v1/admin/users/${encodeURIComponent(t.dataset.disable)}/disable`, { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Disable failed");
        await load();
      } catch (err) {
        msg.textContent = (err && err.message) ? err.message : "Disable failed";
      }
    }
  });

  if (btn) btn.addEventListener("click", load);
  load();
}

async function loadEmbedKey() {
  const maskedEl = document.getElementById("embedKeyMasked");
  const linkEl = document.getElementById("embedInstallLink");
  const snippetEl = document.getElementById("embedSnippet");
  const msgEl = document.getElementById("embedMsg");
  if (!maskedEl || !linkEl || !snippetEl) return;

  try {
    if (msgEl) msgEl.textContent = "Loading widget key...";
    const res = await apiFetch("/api/v1/embed/keys/primary", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || ("Failed to load widget key (" + res.status + ")"));
    maskedEl.textContent = data.masked_key || "-";

    // Store real snippet for copy, and also show real snippet as requested.
    window.__reaiEmbedSnippet = String(data.install_snippet || "");
    window.__reaiEmbedInstallUrl = String(data.install_script_url || "");
    // Try to extract the real key from the URL (so "Copy key" can copy the full value).
    window.__reaiEmbedKey = "";
    try {
      const u = new URL(window.__reaiEmbedInstallUrl);
      window.__reaiEmbedKey = u.searchParams.get("key") || "";
    } catch (_) {}
    linkEl.textContent = String(data.install_script_url || "-");
    linkEl.href = data.install_script_url || "#";
    snippetEl.textContent = String(data.install_snippet || "");
    if (msgEl) msgEl.textContent = "Ready. Paste the snippet into your website <head> or before </body>.";
  } catch (err) {
    if (msgEl) msgEl.textContent = (err && err.message) ? err.message : "Login required (or API not ready).";
  }
}

function onDashboardWidget() {
  const btn = document.getElementById("refreshEmbedKey");
  const copyBtn = document.getElementById("copyEmbedSnippet");
  const copyKeyBtn = document.getElementById("copyEmbedKey");
  if (btn) btn.addEventListener("click", loadEmbedKey);
  if (copyBtn) copyBtn.addEventListener("click", async () => {
    const msgEl = document.getElementById("embedMsg");
    const s = String(window.__reaiEmbedSnippet || "");
    if (!s) {
      if (msgEl) msgEl.textContent = "Snippet not ready yet.";
      return;
    }
    try {
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(s);
      } else {
        const ta = document.createElement("textarea");
        ta.value = s;
        ta.style.position = "fixed";
        ta.style.left = "-1000px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      if (msgEl) msgEl.textContent = "Snippet copied.";
    } catch (e) {
      if (msgEl) msgEl.textContent = "Copy failed. Open the install link and copy from the address bar.";
    }
  });
  if (copyKeyBtn) copyKeyBtn.addEventListener("click", async () => {
    const msgEl = document.getElementById("embedMsg");
    const k = String(window.__reaiEmbedKey || "");
    if (!k) {
      if (msgEl) msgEl.textContent = "Key not ready yet.";
      return;
    }
    try {
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(k);
      } else {
        const ta = document.createElement("textarea");
        ta.value = k;
        ta.style.position = "fixed";
        ta.style.left = "-1000px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      if (msgEl) msgEl.textContent = "Key copied.";
    } catch (e) {
      if (msgEl) msgEl.textContent = "Copy failed.";
    }
  });
  loadEmbedKey();
}

document.addEventListener("DOMContentLoaded", () => {
  const page = (document.body && document.body.dataset && document.body.dataset.page) ? document.body.dataset.page : "";
  if (page === "login") onLoginPage();
  if (page === "dashboard") { onDashboardPage(); onDashboardChart(); onDashboardWidget(); }
  if (page === "leads") onLeadsPage();
  if (page === "integrations") onIntegrationsPage();
  if (page === "appointments") onAppointmentsPage();
  if (page === "audit") onAuditPage();
  if (page === "register") onRegisterPage();
  if (page === "billing") onBillingPage();
  if (page === "forgot") onForgotPasswordPage();
  if (page === "reset") onResetPasswordPage();
  if (page === "admin") onAdminPage();
});
