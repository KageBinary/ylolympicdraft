"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, clearToken } from "../../../lib/api";

type DraftState = {
  complete: boolean;
  event: null | {
    id: string;
    sport: string;
    name: string;
    event_key: string;
    is_team_event: boolean;
    sort_order: number;
  };
  event_index: number | null;
  direction: "forward" | "reverse" | null;
  members: Array<{ id: string; username: string; draft_position: number | null }>;
  picks: Array<{
    user_id: string;
    username: string;
    entry_key: string;
    entry_name: string;
    picked_at: string;
  }>;
  on_the_clock: null | { id: string; username: string };
};

type Entry = {
  id?: string;
  event_id: string;
  entry_key: string;
  entry_name: string;
  country_code?: string | null;
  is_team?: boolean;
};

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

function Card({
  title,
  children,
  right,
}: {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/70 bg-white/85 p-4 shadow-lg shadow-slate-900/5 backdrop-blur">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-black uppercase tracking-[0.12em] text-slate-700">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export default function DraftRoomPage() {
  const r = useRouter();
  const params = useParams<{ leagueId: string }>();
  const leagueId = params.leagueId;

  const [state, setState] = useState<DraftState | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [pickLoading, setPickLoading] = useState(false);

  const [myPicks, setMyPicks] = useState<MyPick[]>([]);
  const [teamLoading, setTeamLoading] = useState(false);

  const pollRef = useRef<number | null>(null);
  const lastEventIdRef = useRef<string | null>(null);

  const selected = useMemo(() => entries.find((e) => e.entry_key === selectedKey) || null, [entries, selectedKey]);
  const takenKeys = useMemo(() => new Set((state?.picks ?? []).map((p) => p.entry_key)), [state?.picks]);

  function logout() {
    clearToken();
    r.push("/login");
  }

  const fetchState = useCallback(async () => {
    try {
      const s = await api<DraftState>(`/draft/state?league_id=${encodeURIComponent(leagueId)}`);
      setState(s);
      setErr(null);
      return s;
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load draft state";
      setErr(message);
      return null;
    }
  }, [leagueId]);

  const fetchEntries = useCallback(async (eventId: string, query: string) => {
    setEntriesLoading(true);
    try {
      const url =
        `/entries/for-event?league_id=${encodeURIComponent(leagueId)}` +
        `&event_id=${encodeURIComponent(eventId)}` +
        `&limit=50` +
        (query.trim() ? `&q=${encodeURIComponent(query.trim())}` : "");

      const out = await api<{ event_id: string; entries: Entry[] }>(url);
      setEntries(out.entries);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load entries";
      setErr(message);
    } finally {
      setEntriesLoading(false);
    }
  }, [leagueId]);

  const fetchMyTeam = useCallback(async () => {
    setTeamLoading(true);
    try {
      const out = await api<MyPicksResponse>(`/me/picks?league_id=${encodeURIComponent(leagueId)}`);
      setMyPicks(out.picks);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load your team";
      setErr(message);
    } finally {
      setTeamLoading(false);
    }
  }, [leagueId]);

  useEffect(() => {
    (async () => {
      const s = await fetchState();
      await fetchMyTeam();

      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(() => {
        fetchState();
        fetchMyTeam();
      }, 2500);

      const evId = s?.event?.id || null;
      lastEventIdRef.current = evId;
      if (evId) fetchEntries(evId, "");
    })();

    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [fetchEntries, fetchMyTeam, fetchState]);

  useEffect(() => {
    const evId = state?.event?.id || null;
    if (!evId) return;

    if (lastEventIdRef.current !== evId) {
      lastEventIdRef.current = evId;
      setQ("");
      setSelectedKey(null);
      setEntries([]);
      fetchEntries(evId, "");
    }
  }, [fetchEntries, state?.event?.id]);

  useEffect(() => {
    const evId = state?.event?.id || null;
    if (!evId) return;

    const t = window.setTimeout(() => {
      fetchEntries(evId, q);
    }, 250);

    return () => window.clearTimeout(t);
  }, [fetchEntries, q, state?.event?.id]);

  useEffect(() => {
    if (selectedKey && takenKeys.has(selectedKey)) {
      setSelectedKey(null);
    }
  }, [selectedKey, takenKeys]);

  async function submitPick() {
    if (!state?.event?.id) return;
    if (!selected) {
      setErr("Select an entry first.");
      return;
    }
    if (takenKeys.has(selected.entry_key)) {
      setErr("That athlete has already been picked.");
      setSelectedKey(null);
      return;
    }

    setPickLoading(true);
    setErr(null);
    try {
      await api("/draft/pick", "POST", {
        league_id: leagueId,
        entry_key: selected.entry_key,
        entry_name: selected.entry_name,
      });

      setSelectedKey(null);
      const s = await fetchState();
      await fetchMyTeam();
      if (s?.event?.id) fetchEntries(s.event.id, "");
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Pick failed";
      setErr(message);
    } finally {
      setPickLoading(false);
    }
  }

  if (!state) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
        <div className="w-full max-w-md rounded-2xl border border-white/70 bg-white/90 p-6 text-center shadow-lg shadow-slate-900/5">
          <h1 className="text-lg font-black uppercase tracking-[0.12em] text-slate-700">Draft room</h1>
          <p className="mt-3 text-sm text-slate-600">
            {err || "Loading draft..."}
          </p>
          <button
            onClick={() => r.push(`/leagues/${leagueId}`)}
            className="mt-4 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50"
          >
            Back to league
          </button>
        </div>
      </main>
    );
  }

  const onClock = state.on_the_clock?.username ?? "--";
  const direction = state.direction ?? "--";
  const event = state.event;
  const lastPick = myPicks.length > 0 ? myPicks[myPicks.length - 1] : null;

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <header className="mx-auto mb-4 flex w-full max-w-6xl items-center justify-between rounded-2xl border border-white/70 bg-white/85 px-4 py-3 shadow-lg shadow-slate-900/5 backdrop-blur">
        <div className="flex items-center gap-2">
          <button
            onClick={() => r.push(`/leagues/${leagueId}`)}
            className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50"
          >
            Back
          </button>
          <button
            onClick={logout}
            className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm font-semibold text-rose-700 hover:bg-rose-100"
          >
            Logout
          </button>
        </div>
        <div className="text-sm font-black uppercase tracking-[0.14em] text-slate-800">Draft room</div>
        <div className="text-xs text-slate-500">League: {leagueId.slice(0, 8)}...</div>
      </header>

      <div className="mx-auto max-w-6xl">
        {err && <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card title="On the clock">
            <div className="text-2xl font-black tracking-tight text-slate-900">{onClock}</div>
            <div className="mt-2 text-xs text-slate-500">
              Direction: <span className="font-semibold uppercase text-slate-700">{direction}</span>
            </div>
          </Card>

          <Card title="Current event">
            {state.complete ? (
              <div className="text-lg font-black text-emerald-700">Draft complete</div>
            ) : (
              <>
                <div className="text-sm font-bold text-slate-900">
                  {event?.sport} - {event?.name}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  event_key: <span className="font-mono text-slate-700">{event?.event_key}</span>
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  Event index: <span className="font-semibold text-slate-700">{state.event_index ?? "--"}</span>
                </div>
              </>
            )}
          </Card>

          <Card title="My team">
            {teamLoading ? (
              <div className="text-sm text-slate-500">Loading...</div>
            ) : (
              <>
                <div className="text-2xl font-black text-slate-900">{myPicks.length}</div>
                <div className="mt-1 text-xs text-slate-500">Total picks made</div>
                {lastPick && (
                  <div className="mt-2 rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600">
                    Latest: <span className="font-semibold text-slate-800">{lastPick.entry_name}</span>
                  </div>
                )}
              </>
            )}
          </Card>

          <Card title="Quick actions">
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => {
                  fetchState();
                  fetchMyTeam();
                }}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50"
              >
                Refresh
              </button>
              <button
                onClick={() => r.push(`/leagues/${leagueId}/team`)}
                className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-100"
              >
                View my team
              </button>
            </div>
            <div className="mt-2 text-xs text-slate-500">Tip: use another browser profile to draft as another user.</div>
          </Card>
        </div>

        {!state.complete && event?.id && (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card
              title="Make a pick"
              right={
                <button
                  disabled={!selected || pickLoading}
                  onClick={submitPick}
                  className="rounded-xl bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {pickLoading ? "Submitting..." : "Submit pick"}
                </button>
              }
            >
              <div className="grid gap-3">
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search entries..."
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
                />

                <div className="rounded-2xl border border-slate-200 bg-white">
                  <div className="max-h-[360px] overflow-auto">
                    {entriesLoading && <div className="p-3 text-sm text-slate-500">Loading...</div>}
                    {!entriesLoading && entries.length === 0 && <div className="p-3 text-sm text-slate-500">No entries found.</div>}

                    {entries.map((en) => {
                      const active = en.entry_key === selectedKey;
                      const taken = takenKeys.has(en.entry_key);
                      return (
                        <button
                          key={en.entry_key}
                          disabled={taken}
                          onClick={() => setSelectedKey(en.entry_key)}
                          className={[
                            "w-full border-b border-slate-100 px-3 py-2 text-left disabled:cursor-not-allowed",
                            taken ? "bg-slate-100 opacity-70" : active ? "bg-sky-50" : "bg-white hover:bg-slate-50",
                          ].join(" ")}
                        >
                          <div className={taken ? "text-sm font-semibold text-slate-500" : "text-sm font-semibold text-slate-900"}>
                            {en.entry_name}
                            {taken && (
                              <span className="ml-2 rounded-full bg-slate-300 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-700">
                                Taken
                              </span>
                            )}
                          </div>
                          <div className="text-xs font-mono text-slate-500">{en.entry_key}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="text-xs text-slate-500">
                  Selected: <span className="font-semibold text-slate-900">{selected ? selected.entry_name : "none"}</span>
                </div>
              </div>
            </Card>

            <Card title="Picks for this event">
              <div className="grid gap-2">
                {state.picks.length === 0 && <div className="text-sm text-slate-500">No picks yet.</div>}
                {state.picks.map((p, idx) => (
                  <div key={`${p.user_id}-${idx}`} className="rounded-2xl border border-slate-200 bg-white p-3">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-black text-slate-900">
                        {idx + 1}. {p.username}
                      </div>
                      <div className="text-xs text-slate-500">{new Date(p.picked_at).toLocaleTimeString()}</div>
                    </div>
                    <div className="mt-1 text-sm text-slate-900">{p.entry_name}</div>
                    <div className="mt-1 text-xs font-mono text-slate-500">{p.entry_key}</div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        <div className="mt-4">
          <Card title="Draft order">
            <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {state.members.map((m) => (
                <li key={m.id} className="rounded-2xl border border-slate-200 bg-white p-3">
                  <div className="text-sm font-black text-slate-900">{m.username}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    Position: <span className="font-semibold text-slate-700">{m.draft_position ?? "--"}</span>
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </main>
  );
}
