"use client";

import { ChangeEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearToken } from "../../lib/api";

type ParsedRow = {
  event_ref: string;
  leaderboard: string[];
};

type ImportResponse = {
  ok: boolean;
  imported_events: number;
  points: Record<string, number>;
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

function parseGlobalResultsCsv(input: string): ParsedRow[] {
  const matrix = parseCsvMatrix(input.trim());
  if (matrix.length < 2) throw new Error("CSV needs a header and at least one data row.");

  const header = matrix[0].map((h) => h.trim().toLowerCase());
  const eventColCandidates = ["event_ref", "event_id", "event_key", "event_name"];
  const eventIdx = eventColCandidates.map((k) => header.indexOf(k)).find((idx) => idx >= 0) ?? -1;
  if (eventIdx < 0) {
    throw new Error("Header must include one of: event_ref, event_id, event_key, event_name");
  }

  const placeKeys = [
    ["first", "place_1", "p1"],
    ["second", "place_2", "p2"],
    ["third", "place_3", "p3"],
    ["fourth", "place_4", "p4"],
    ["fifth", "place_5", "p5"],
    ["sixth", "place_6", "p6"],
    ["seventh", "place_7", "p7"],
    ["eighth", "place_8", "p8"],
    ["ninth", "place_9", "p9"],
    ["tenth", "place_10", "p10"],
  ];
  const placeIdx: number[] = [];
  for (const aliases of placeKeys) {
    const idx = aliases.map((k) => header.indexOf(k)).find((i) => i >= 0) ?? -1;
    if (idx < 0) throw new Error(`Missing place column. Need one of: ${aliases.join(", ")}`);
    placeIdx.push(idx);
  }

  const rows: ParsedRow[] = [];
  for (let r = 1; r < matrix.length; r++) {
    const lineNo = r + 1;
    const row = matrix[r];
    const eventRef = (row[eventIdx] ?? "").trim();
    if (!eventRef) throw new Error(`Row ${lineNo}: missing event reference`);

    const leaderboard = placeIdx.map((idx) => (row[idx] ?? "").trim());
    if (leaderboard.some((name) => !name)) throw new Error(`Row ${lineNo}: all 10 leaderboard names are required`);
    if (new Set(leaderboard.map((n) => n.toLowerCase())).size !== leaderboard.length) {
      throw new Error(`Row ${lineNo}: duplicate names in leaderboard`);
    }

    rows.push({ event_ref: eventRef, leaderboard });
  }

  return rows;
}

export default function GlobalResultsAdminPage() {
  const r = useRouter();
  const [csvText, setCsvText] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const parsed = useMemo(() => {
    if (!csvText.trim()) return null;
    try {
      return { rows: parseGlobalResultsCsv(csvText), error: null as string | null };
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Invalid CSV";
      return { rows: null, error: message };
    }
  }, [csvText]);

  async function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setCsvText(text);
    e.target.value = "";
  }

  async function importCsv() {
    if (!parsed?.rows) return;
    setLoading(true);
    setErr(null);
    setOk(null);
    try {
      const out = await api<ImportResponse>("/admin/results/import-global", "POST", {
        admin_password: adminPassword || null,
        rows: parsed.rows,
      });
      setOk(`Imported ${out.imported_events} events.`);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Import failed";
      setErr(message);
      if (message.toLowerCase().includes("not authenticated")) {
        clearToken();
        r.push("/login");
      }
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    clearToken();
    r.push("/login");
  }

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

        <h1 className="mt-4 text-3xl font-black text-slate-900 sm:text-4xl">Global Results Admin</h1>
        <p className="mt-2 text-sm text-slate-600">Single source of truth for all leagues. One row per event, 10 ranked names.</p>

        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
          CSV headers example: <span className="font-mono">event_key,first,second,third,fourth,fifth,sixth,seventh,eighth,ninth,tenth</span>
        </div>

        <div className="mt-4">
          <label className="text-sm font-semibold text-slate-700">Admin password (if enabled)</label>
          <input
            type="password"
            value={adminPassword}
            onChange={(e) => setAdminPassword(e.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
          />
        </div>

        <div className="mt-4 flex items-center gap-2">
          <input type="file" accept=".csv,text/csv" onChange={onFileChange} className="text-sm text-slate-700" />
        </div>

        <textarea
          value={csvText}
          onChange={(e) => setCsvText(e.target.value)}
          placeholder="event_key,first,second,third,fourth,fifth,sixth,seventh,eighth,ninth,tenth"
          className="mt-3 min-h-[280px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-200"
        />

        {parsed?.error && <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{parsed.error}</div>}
        {parsed?.rows && (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
            Parsed <span className="font-semibold">{parsed.rows.length}</span> event rows.
          </div>
        )}
        {err && <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{err}</div>}
        {ok && <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{ok}</div>}

        <div className="mt-4">
          <button
            onClick={importCsv}
            disabled={!parsed?.rows || !!parsed.error || loading}
            className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Importing..." : "Import global results"}
          </button>
        </div>
      </section>
    </main>
  );
}
