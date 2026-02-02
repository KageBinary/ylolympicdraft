"use client";

import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen px-4 py-10 sm:px-6 lg:px-8">
      <section className="mx-auto grid w-full max-w-6xl gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="rounded-3xl border border-white/70 bg-white/80 p-8 shadow-xl shadow-sky-900/10 backdrop-blur sm:p-10">
          <div className="inline-flex rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-sky-700">
            Snake Draft Platform
          </div>
          <h1 className="mt-5 text-4xl font-black leading-tight text-slate-900 sm:text-5xl">
            Build your own
            <br />
            Olympic fantasy draft
          </h1>
          <p className="mt-5 max-w-xl text-base text-slate-600 sm:text-lg">
            Create a league, invite friends, and draft athletes event-by-event with live order updates.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/register"
              className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              Create account
            </Link>
            <Link
              href="/login"
              className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:border-slate-400 hover:bg-slate-50"
            >
              Login
            </Link>
            <Link
              href="/leagues"
              className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-2.5 text-sm font-semibold text-emerald-800 transition hover:-translate-y-0.5 hover:bg-emerald-100"
            >
              Open leagues
            </Link>
          </div>
          <p className="mt-6 text-sm text-slate-500">
            Already logged in? Jump to <span className="font-mono text-slate-700">/leagues</span>.
          </p>
        </div>

        <aside className="rounded-3xl border border-white/70 bg-gradient-to-b from-slate-900 to-slate-800 p-8 text-white shadow-xl shadow-slate-900/30 sm:p-10">
          <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-sky-200">
            How it works
          </h2>
          <ol className="mt-5 grid gap-4 text-sm">
            <li className="rounded-xl border border-white/15 bg-white/5 p-4">
              <span className="text-sky-200">01</span> Create a league and set draft rounds.
            </li>
            <li className="rounded-xl border border-white/15 bg-white/5 p-4">
              <span className="text-sky-200">02</span> Share your invite code with friends.
            </li>
            <li className="rounded-xl border border-white/15 bg-white/5 p-4">
              <span className="text-sky-200">03</span> Draft event-by-event in live snake order.
            </li>
          </ol>
        </aside>
      </section>
    </main>
  );
}
