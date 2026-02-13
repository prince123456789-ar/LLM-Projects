"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("admin@agency.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault(); setError(""); setLoading(true);
    try { const tokens = await login(email, password); localStorage.setItem("token", tokens.access_token); localStorage.setItem("refresh_token", tokens.refresh_token); router.push("/dashboard"); }
    catch (err) { setError(err instanceof Error ? err.message : "Login failed"); }
    finally { setLoading(false); }
  }

  return <main className="container main-shell"><section className="card" style={{ maxWidth: "560px", margin: "0 auto" }}><h1>Welcome Back</h1><p className="small">Sign in to access lead routing, team dashboards, and integrations.</p><form className="grid" onSubmit={onSubmit}><input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" /><input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Password" /><button type="submit">{loading ? "Signing in..." : "Sign In"}</button></form>{error ? <p className="small" style={{ marginTop: "10px" }}>{error}</p> : null}</section></main>;
}