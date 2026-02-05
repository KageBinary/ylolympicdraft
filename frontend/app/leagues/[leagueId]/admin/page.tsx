"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, clearToken } from "../../../lib/api";

type Me = {
  id: string;
  username: string;
};

type League = {
  id: string;
  code: string;
  name: string;
  status: "lobby" | "drafting" | "locked" | string;
  commissioner_id: string;
  draft_rounds: number;
  created_at: string;
};

type LeagueDetailResponse = {
  league: League | null;
  members: Array<{ id: string; username: string; joined_at: string; draft_position: number | null }>;
};

type EventRow = {
  id: string;
  sport: string;
  name: string;
  event_key: string;
  is_team_event: boolean;
  sort_order: number;
};

type CsvPlacement = {
  event_key: string;
  place: number;
  entry_key: string;
  entry_name: string;
};

type ParsedCsv = {
  rows: CsvPlacement[];
  groups: Map<string, CsvPlacement[]>;
};

type ImportLog = {
  event_key: string;
  ok: boolean;
  message: string;
};

function parseCsvMatrix(input: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < input.length; i++) {
    const ch = input[i];
    const next = i + 1 < input.length ? input[i + 1] : "";

    if (ch === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (!inQuotes && ch === ",") {
      row.push(cell);
      cell = "";
      continue;
    }

    if (!inQuotes && (ch === "\n" || ch === "\r")) {
      if (ch === "\r" && next === "\n") i++;
      row.push(cell);
      cell = "";
      if (row.some((c) => c.trim().length > 0)) rows.push(row);
      row = [];
      continue;
    }

    cell += ch;
  }

  row.push(cell);
  if (row.some((c) => c.trim().length > 0)) rows.push(row);
  return rows;
}

function parsePlacementsCsv(input: string): ParsedCsv {
  const matrix = parseCsvMatrix(input.trim());
  if (matrix.length < 2) {
    throw new Error("CSV must include header + at least one data row.");
  }

  const header = matrix[0].map((h) => h.trim().toLowerCase());
  const required = ["event_key", "place", "entry_key", "entry_name"] as const;
  for (const col of required) {
    if (!header.includes(col)) {
      throw new Error(`Missing required CSV column: ${col}`);
    }
  }

  const idx = {
    event_key: header.indexOf("event_key"),
    place: header.indexOf("place"),
    entry_key: header.indexOf("entry_key"),
    entry_name: header.indexOf("entry_name"),
  };

  const rows: CsvPlacement[] = [];
  for (let i = 1; i < matrix.length; i++) {
    const lineNo = i + 1;
    const row = matrix[i];
    const event_key = (row[idx.event_key] ?? "").trim();
    const placeText = (row[idx.place] ?? "").trim();
    const entry_key = (row[idx.entry_key] ?? "").trim();
    const entry_name = (row[idx.entry_name] ?? "").trim();

    if (!event_key || !placeText || !entry_key || !entry_name) {
      throw new Error(`Row ${lineNo}: missing required value.`);
    }

    const place = Number(placeText);
    if (!Number.isInteger(place) || place < 1 || place > 10) {
      throw new Error(`Row ${lineNo}: place must be an integer from 1 to 10.`);
    }

    rows.push({ event_key, place, entry_key, entry_name });
  }

  const groups = new Map<string, CsvPlacement[]>();
  for (const row of rows) {
    const list = groups.get(row.event_key) ?? [];
    list.push(row);
    groups.set(row.event_key, list);
  }

  for (const [eventKey, list] of groups.entries()) {
    const sortedPlaces = [...list.map((r) => r.place)].sort((a, b) => a - b);
    if (new Set(sortedPlaces).size !== sortedPlaces.length) {
      throw new Error(`${eventKey}: duplicate place values.`);
    }
    const expected = Array.from({ length: sortedPlaces[sortedPlaces.length - 1] }, (_, i) => i + 1);
    if (JSON.stringify(sortedPlaces) !== JSON.stringify(expected)) {
      throw new Error(`${eventKey}: places must be contiguous from 1.`);
    }
    const keys = list.map((r) => r.entry_key);
    if (new Set(keys).size !== keys.length) {
      throw new Error(`${eventKey}: duplicate entry_key values.`);
    }
  }

  return { rows, groups };
}

export default function LeagueAdminPage() {
  const r = useRouter();
  const params = useParams<{ leagueId: string }>();
  const leagueId = params.leagueId;

  const [me, setMe] = useState<Me | null>(null);
  const [detail, setDetail] = useState<LeagueDetailResponse | null>(null);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [csvText, setCsvText] = useState("");
  const [loading, setLoading] = useState(true);
  const [locking, setLocking] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [logs, setLogs] = useState<ImportLog[]>([]);

  async function load() {
    setErr(null);
    setLoading(true);
    try {
      const [meOut, detailOut, eventsOut] = await Promise.all([
        api<Me>("/me"),
        api<LeagueDetailResponse>(`/leagues/${leagueId}`),
        api<EventRow[]>("/events/"),
      ]);
      setMe(meOut);
      setDetail(detailOut);
      setEvents(eventsOut);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load admin page";
      setErr(msg);
      if (msg.toLowerCase().includes("not authenticated")) {
        clearToken();
        r.push("/login");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId]);

  const parsed = useMemo(() => {
    if (!csvText.trim()) return null;
    try {
      return { data: parsePlacementsCsv(csvText), error: null as string | null };
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Invalid CSV";
      return { data: null, error: message };
    }
  }, [csvText]);

  const league = detail?.league ?? null;
  const isCommissioner = !!league && !!me && String(league.commissioner_id) === String(me.id);
  const eventByKey = useMemo(() => {
    const map = new Map<string, EventRow>();
    for (const ev of events) map.set(ev.event_key, ev);
    return map;
  }, [events]);

  const eventKeysInCsv = parsed?.data ? Array.from(parsed.data.groups.keys()) : [];
  const unknownEventKeys = eventKeysInCsv.filter((k) => !eventByKey.has(k));

  async function lockLeague() {
    if (!league) return;
    setErr(null);
    setLocking(true);
    try {
      await api(`/leagues/${league.id}/lock`, "POST");
      await load();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to lock league";
      setErr(message);
    } finally {
      setLocking(false);
    }
  }

  async function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setCsvText(text);
    e.target.value = "";
  }

  async function submitImport() {
    if (!league || !parsed?.data) return;
    setSubmitting(true);
    setErr(null);
    setLogs([]);

    const nextLogs: ImportLog[] = [];
    try {
      const groups = Array.from(parsed.data.groups.entries()).sort(([a], [b]) => a.localeCompare(b));
      for (const [eventKey, placements] of groups) {
        const ev = eventByKey.get(eventKey);
        if (!ev) {
          nextLogs.push({ event_key: eventKey, ok: false, message: "event_key not found in events table" });
          continue;
        }

        try {
          await api("/results/submit", "POST", {
            league_id: league.id,
            event_id: ev.id,
            placements: placements
              .map((p) => ({ place: p.place, entry_key: p.entry_key, entry_name: p.entry_name }))
              .sort((a, b) => a.place - b.place),
          });
          nextLogs.push({ event_key: eventKey, ok: true, message: `Imported ${placements.length} placements` });
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : "Import failed";
          nextLogs.push({ event_key: eventKey, ok: false, message });
        }
      }
      setLogs(nextLogs);
    } finally {
      setSubmitting(false);
    }
  }

  function logout() {
    clearToken();
    r.push("/login");
  }

  if (loading) {
    return (
      <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl rounded-2xl border border-white/70 bg-white/80 p-5 text-sm text-slate-600 shadow-lg shadow-sky-900/10">
          Loading admin...
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-5xl rounded-3xl border border-white/70 bg-white/80 p-6 shadow-xl shadow-sky-900/10 backdrop-blur sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => r.push(`/leagues/${leagueId}`)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
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
          <button
            onClick={load}
            className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50"
          >
            Refresh
          </button>
        </div>

        <h1 className="mt-4 text-3xl font-black text-slate-900 sm:text-4xl">League Admin</h1>
        <p className="mt-2 text-sm text-slate-600">Commissioner tools for locking league and importing event results via CSV.</p>

        {err && <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}

        {!league ? (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">League not found.</div>
        ) : !isCommissioner ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Commissioner-only page. You can view this page, but imports are blocked for non-commissioners.
          </div>
        ) : (
          <>
            <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-black text-slate-900">League status</p>
                  <p className="text-xs text-slate-500">
                    Current status: <span className="font-semibold text-slate-700">{league.status}</span>
                  </p>
                </div>
                {league.status === "drafting" && (
                  <button
                    onClick={lockLeague}
                    disabled={locking}
                    className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {locking ? "Locking..." : "Lock league"}
                  </button>
                )}
              </div>
              {league.status !== "locked" && (
                <p className="mt-2 text-xs text-amber-700">Results import requires `locked` status. Lock the league first.</p>
              )}
            </section>

            <section className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-sm font-black text-slate-900">Import results CSV</p>
              <p className="mt-1 text-xs text-slate-500">Required columns: `event_key,place,entry_key,entry_name`</p>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input type="file" accept=".csv,text/csv" onChange={onFileChange} className="text-sm text-slate-700" />
              </div>

              <textarea
                value={csvText}
                onChange={(e) => setCsvText(e.target.value)}
                placeholder="event_key,place,entry_key,entry_name&#10;biathlon_mens_10km_sprint,1,ath:12345,John Doe"
                className="mt-3 min-h-[220px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
              />

              {parsed?.error && <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{parsed.error}</div>}

              {parsed?.data && (
                <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  Parsed rows: <span className="font-semibold">{parsed.data.rows.length}</span>; events:{" "}
                  <span className="font-semibold">{parsed.data.groups.size}</span>
                  {unknownEventKeys.length > 0 && (
                    <div className="mt-2 text-amber-700">
                      Unknown event_key values: <span className="font-mono">{unknownEventKeys.join(", ")}</span>
                    </div>
                  )}
                </div>
              )}

              <div className="mt-3">
                <button
                  onClick={submitImport}
                  disabled={!parsed?.data || !!parsed.error || submitting || league.status !== "locked"}
                  className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {submitting ? "Importing..." : "Import results"}
                </button>
              </div>

              {logs.length > 0 && (
                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
                  <p className="text-sm font-bold text-slate-900">Import log</p>
                  <ul className="mt-2 grid gap-2 text-sm">
                    {logs.map((log) => (
                      <li
                        key={log.event_key}
                        className={`rounded-lg border px-2 py-1.5 ${
                          log.ok ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-700"
                        }`}
                      >
                        <span className="font-mono">{log.event_key}</span>: {log.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
