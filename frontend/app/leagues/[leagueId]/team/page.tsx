"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, clearToken } from "../../../lib/api";

type MyPick = {
  event_id: string;
  sort_order: number;
  sport: string;
  event_name: string;
  entry_key: string;
  entry_name: string;
  picked_at: string;
};

type MyPicksResponse = {
  league_id: string;
  user_id: string;
  picks: MyPick[];
};

export default function TeamPage() {
  const r = useRouter();
  const params = useParams<{ leagueId: string }>();
  const leagueId = params.leagueId;

  const [picks, setPicks] = useState<MyPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const out = await api<MyPicksResponse>(`/me/picks?league_id=${encodeURIComponent(leagueId)}`);
      setPicks(out.picks);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load your team";
      setErr(message);
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  function logout() {
    clearToken();
    r.push("/login");
  }

  useEffect(() => {
    load();
  }, [load]);

  const groupedBySport = useMemo(() => {
    const map = new Map<string, MyPick[]>();
    for (const pick of picks) {
      const current = map.get(pick.sport) || [];
      current.push(pick);
      map.set(pick.sport, current);
    }
    return Array.from(map.entries());
  }, [picks]);

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-6xl rounded-3xl border border-white/70 bg-white/85 p-6 shadow-xl shadow-slate-900/10 backdrop-blur sm:p-8">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => r.push(`/leagues/${leagueId}`)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50"
            >
              Back
            </button>
            <button
              onClick={() => r.push(`/leagues/${leagueId}/draft`)}
              className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-1.5 text-sm font-semibold text-sky-700 hover:bg-sky-100"
            >
              Draft room
            </button>
            <button
              onClick={logout}
              className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm font-semibold text-rose-700 hover:bg-rose-100"
            >
              Logout
            </button>
          </div>

          <button
            onClick={load}
            className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50"
          >
            Refresh
          </button>
        </header>

        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Roster</p>
          <h1 className="mt-1 text-3xl font-black text-slate-900">My Team</h1>
          <p className="mt-2 text-sm text-slate-600">Track everything you have drafted in this league.</p>
          <div className="mt-3 inline-flex rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
            Total picks: {picks.length}
          </div>
        </div>

        {err && <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

        {loading ? (
          <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-500">Loading your team...</div>
        ) : picks.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
            No picks yet. Go to the draft room and make your first pick.
          </div>
        ) : (
          <div className="mt-5 grid gap-5">
            {groupedBySport.map(([sport, sportPicks]) => (
              <section key={sport} className="rounded-2xl border border-slate-200 bg-white p-4">
                <h2 className="text-lg font-black text-slate-900">{sport}</h2>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {sportPicks.map((pick) => (
                    <article key={`${pick.event_id}-${pick.entry_key}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{pick.event_name}</p>
                      <p className="mt-1 text-sm font-bold text-slate-900">{pick.entry_name}</p>
                      <p className="mt-1 text-xs font-mono text-slate-500">{pick.entry_key}</p>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
