"use client";

import { useEffect, useState } from "react";
import { api, clearToken } from "../lib/api";
import { useRouter } from "next/navigation";

type League = {
  id: string;
  code: string;
  name: string;
  status: string;
  commissioner_id: string;
  created_at: string;
};

export default function LeaguesPage() {
  const r = useRouter();
  const [leagues, setLeagues] = useState<League[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [createName, setCreateName] = useState("YL Olympic Draft");
  const [draftRounds, setDraftRounds] = useState(20);
  const [joinCode, setJoinCode] = useState("");

  async function load() {
    setErr(null);
    try {
      const out = await api<League[]>("/leagues/mine");
      setLeagues(out);
    } catch (e: any) {
      setErr(e.message || "Failed to load leagues");
      if ((e.message || "").toLowerCase().includes("not authenticated")) {
        clearToken();
        r.push("/login");
      }
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createLeague() {
    setErr(null);
    try {
      const league = await api<any>("/leagues/create", "POST", { name: createName, draft_rounds: draftRounds });
      await load();
      r.push(`/leagues/${league.id}`);
    } catch (e: any) {
      setErr(e.message || "Create failed");
    }
  }

  async function joinLeague() {
    setErr(null);
    try {
      await api<any>("/leagues/join", "POST", { code: joinCode });
      await load();
      setJoinCode("");
    } catch (e: any) {
      setErr(e.message || "Join failed");
    }
  }

  function logout() {
    clearToken();
    r.push("/login");
  }

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-6xl">
        <div className="rounded-3xl border border-white/70 bg-white/80 p-6 shadow-xl shadow-sky-900/10 backdrop-blur sm:p-8">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">League Hub</p>
              <h1 className="mt-1 text-3xl font-black text-slate-900 sm:text-4xl">My Leagues</h1>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => r.push("/admin/results")}
                className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800 hover:bg-amber-100"
              >
                Global admin
              </button>
              <button
                onClick={logout}
                className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100"
              >
                Logout
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <section className="rounded-2xl border border-sky-100 bg-sky-50/70 p-4">
              <h2 className="text-sm font-extrabold uppercase tracking-[0.14em] text-sky-800">Create league</h2>
              <div className="mt-3 grid gap-3">
                <input
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  className="w-full rounded-xl border border-sky-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
                />
                <label className="grid gap-1.5 text-sm font-medium text-slate-700">
                  Draft rounds
                  <input
                    type="number"
                    min={1}
                    max={116}
                    value={draftRounds}
                    onChange={(e) => setDraftRounds(parseInt(e.target.value || "20", 10))}
                    className="w-full rounded-xl border border-sky-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
                  />
                </label>
                <button
                  onClick={createLeague}
                  className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800"
                >
                  Create
                </button>
              </div>
            </section>

            <section className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
              <h2 className="text-sm font-extrabold uppercase tracking-[0.14em] text-emerald-800">Join league</h2>
              <div className="mt-3 grid gap-3">
                <input
                  placeholder="YL-XXXXXX"
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                  className="w-full rounded-xl border border-emerald-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200"
                />
                <button
                  onClick={joinLeague}
                  className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-emerald-500"
                >
                  Join
                </button>
              </div>
            </section>
          </div>

          {err && <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}

          <section className="mt-8">
            <h2 className="text-lg font-black text-slate-900">Your leagues</h2>
            <div className="mt-3 grid gap-3">
              {leagues.map((l) => (
                <button
                  key={l.id}
                  onClick={() => r.push(`/leagues/${l.id}`)}
                  className="rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <strong className="text-base text-slate-900">{l.name}</strong>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
                      {l.status}
                    </span>
                  </div>
                  <div className="mt-2 text-sm text-slate-600">
                    Invite code: <span className="font-mono text-slate-800">{l.code}</span>
                  </div>
                </button>
              ))}
              {leagues.length === 0 && (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white/65 p-6 text-sm text-slate-500">
                  No leagues yet. Create one to start drafting.
                </div>
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
