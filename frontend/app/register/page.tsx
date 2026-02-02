"use client";

import Link from "next/link";
import { useState } from "react";
import { api, setToken } from "../lib/api";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
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
      const out = await api<{ access_token: string }>("/auth/register", "POST", { username, password });
      setToken(out.access_token);
      r.push("/leagues");
    } catch (e: any) {
      setErr(e.message || "Register failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-10 sm:px-6">
      <section className="mx-auto w-full max-w-md rounded-3xl border border-white/75 bg-white/85 p-7 shadow-xl shadow-sky-900/10 backdrop-blur sm:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">Get started</p>
        <h1 className="mt-2 text-3xl font-black text-slate-900">Create account</h1>
        <p className="mt-2 text-sm text-slate-600">Start your first league in under a minute.</p>

        <form onSubmit={onSubmit} className="mt-6 grid gap-3">
          <input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200"
          />
          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200"
          />
          <button
            disabled={loading}
            type="submit"
            className="mt-1 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Creating..." : "Create account"}
          </button>
          {err && <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
        </form>

        <p className="mt-5 text-sm text-slate-600">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-slate-900 underline decoration-emerald-300 underline-offset-4">
            Login
          </Link>
        </p>
      </section>
    </main>
  );
}
