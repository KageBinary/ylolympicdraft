"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, clearToken } from "../../../lib/api";

type LeaderboardRow = {
  user_id: string;
  username: string;
  points: number;
};

type LeaderboardResponse = {
  league_id: string;
  scoring: Record<string, number>;
  rows: LeaderboardRow[];
};

export default function LeagueLeaderboardPage() {
  const r = useRouter();
  const params = useParams<{ leagueId: string }>();
  const leagueId = params.leagueId;

  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const out = await api<LeaderboardResponse>(`/results/leaderboard?league_id=${encodeURIComponent(leagueId)}`);
      setRows(out.rows || []);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load leaderboard";
      setErr(message);
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useEffect(() => {
    load();
  }, [load]);

  function logout() {
    clearToken();
    r.push("/login");
  }

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-4xl rounded-3xl border border-white/70 bg-white/85 p-6 shadow-xl shadow-slate-900/10 backdrop-blur sm:p-8">
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
              onClick={() => r.push(`/leagues/${leagueId}/team`)}
              className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 hover:bg-emerald-100"
            >
              My team
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
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">League standings</p>
          <h1 className="mt-1 text-3xl font-black text-slate-900">Leaderboard</h1>
        </div>

        {err && <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

        {loading ? (
          <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-500">Loading leaderboard...</div>
        ) : rows.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
            No leaderboard rows yet.
          </div>
        ) : (
          <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            {rows.map((row, idx) => (
              <div
                key={row.user_id}
                className="grid grid-cols-[72px_1fr_100px] items-center border-b border-slate-100 px-4 py-3 last:border-b-0"
              >
                <div className="text-sm font-black text-slate-700">#{idx + 1}</div>
                <div className="text-sm font-semibold text-slate-900">{row.username}</div>
                <div className="text-right text-sm font-black text-slate-800">{row.points} pts</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
