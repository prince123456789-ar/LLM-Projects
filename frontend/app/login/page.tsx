"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("admin@agency.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const router = useRouter();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const tokens = await login(email, password);
      localStorage.setItem("token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <main className="container">
      <form className="card" onSubmit={onSubmit}>
        <h2>Sign In</h2>
        <p className="small">Use a registered user from the backend.</p>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Password" />
        <button type="submit">Login</button>
        {error ? <p className="small">{error}</p> : null}
      </form>
    </main>
  );
}
