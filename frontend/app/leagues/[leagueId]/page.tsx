"use client";

import { useEffect, useState } from "react";
import { api, clearToken } from "../../lib/api";
import { useRouter, useParams } from "next/navigation";

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

export default function LeagueDetailPage() {
  const r = useRouter();
  const params = useParams<{ leagueId: string }>();
  const leagueId = params.leagueId;

  const [data, setData] = useState<any>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    try {
      const out = await api<any>(`/leagues/${leagueId}`);
      setData(out);
      try {
        const lb = await api<LeaderboardResponse>(`/results/leaderboard?league_id=${encodeURIComponent(leagueId)}`);
        setLeaderboard(lb.rows || []);
      } catch {
        setLeaderboard([]);
      }
    } catch (e: any) {
      setErr(e.message || "Failed");
    }
  }

  useEffect(() => {
    load();
  }, [leagueId]);

  async function startDraft() {
    setErr(null);
    try {
      await api<any>(`/leagues/${leagueId}/start`, "POST");
      await load();
      r.push(`/leagues/${leagueId}/draft`);
    } catch (e: any) {
      setErr(e.message || "Failed to start draft");
    }
  }

  function logout() {
    clearToken();
    r.push("/login");
  }

  if (!data) {
    return (
      <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl rounded-2xl border border-white/70 bg-white/80 p-5 text-sm text-slate-600 shadow-lg shadow-sky-900/10">
          Loading...
        </div>
      </main>
    );
  }

  const draftStarted = data.league?.status !== "lobby";
  const leader = leaderboard.length > 0 ? leaderboard[0] : null;

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-5xl rounded-3xl border border-white/70 bg-white/80 p-6 shadow-xl shadow-sky-900/10 backdrop-blur sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            onClick={() => r.push("/leagues")}
            className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            Back to leagues
          </button>
          <button
            onClick={logout}
            className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm font-semibold text-rose-700 hover:bg-rose-100"
          >
            Logout
          </button>
        </div>

        <h1 className="mt-4 text-3xl font-black text-slate-900 sm:text-4xl">{data.league?.name}</h1>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-slate-700">
            Status: {data.league?.status}
          </span>
          <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-sky-700">
            Code: {data.league?.code}
          </span>
        </div>

        {err && <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            onClick={() => r.push(`/leagues/${leagueId}/draft`)}
            className={`rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition ${
              draftStarted
                ? "bg-slate-900 hover:-translate-y-0.5 hover:bg-slate-800"
                : "cursor-not-allowed bg-slate-300"
            }`}
            disabled={!draftStarted}
          >
            Open draft room
          </button>
          {!draftStarted && (
            <span className="flex items-center text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
              Start the draft first
            </span>
          )}
          <button
            onClick={() => r.push(`/leagues/${leagueId}/team`)}
            className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-semibold text-emerald-700 transition hover:-translate-y-0.5 hover:bg-emerald-100"
          >
            View my team
          </button>
          <button
            onClick={() => r.push(`/leagues/${leagueId}/leaderboard`)}
            className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-700 transition hover:-translate-y-0.5 hover:bg-amber-100"
          >
            Leaderboard
          </button>
          {data.league?.status === "lobby" && (
            <button
              onClick={startDraft}
              className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-emerald-500"
            >
              Start draft
            </button>
          )}
        </div>

        <h2 className="mt-8 text-lg font-black text-slate-900">Current leader</h2>
        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {leader ? (
            <>
              <span className="font-black">{leader.username}</span>
              <span className="ml-2 text-amber-700">({leader.points} pts)</span>
            </>
          ) : (
            <span className="text-amber-800">No leaderboard data yet.</span>
          )}
        </div>

        <h2 className="mt-8 text-lg font-black text-slate-900">Members</h2>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {data.members?.map((m: any) => (
            <li key={m.id} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
              <span className="font-semibold text-slate-900">{m.username}</span>{" "}
              {m.draft_position ? <span className="text-slate-500">(position {m.draft_position})</span> : null}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
