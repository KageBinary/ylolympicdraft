"use client";

import Link from "next/link";
import { useState } from "react";
import { api, setToken } from "../lib/api";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const r = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const out = await api<{ access_token: string }>("/auth/login-json", "POST", {
        username,
        password,
      });
      setToken(out.access_token);
      r.push("/leagues");
    } catch (e: any) {
      setErr(e.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-10 sm:px-6">
      <section className="mx-auto w-full max-w-md rounded-3xl border border-white/75 bg-white/85 p-7 shadow-xl shadow-sky-900/10 backdrop-blur sm:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-sky-700">Welcome back</p>
        <h1 className="mt-2 text-3xl font-black text-slate-900">Login</h1>
        <p className="mt-2 text-sm text-slate-600">Continue to your leagues and draft room.</p>

        <form onSubmit={onSubmit} className="mt-6 grid gap-3">
          <input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
          />
          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
          />
          <button
            disabled={loading}
            type="submit"
            className="mt-1 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Logging in..." : "Login"}
          </button>
          {err && <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
        </form>

        <p className="mt-5 text-sm text-slate-600">
          No account?{" "}
          <Link href="/register" className="font-semibold text-slate-900 underline decoration-sky-300 underline-offset-4">
            Register
          </Link>
        </p>
      </section>
    </main>
  );
}
