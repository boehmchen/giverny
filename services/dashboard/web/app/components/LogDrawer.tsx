"use client";

import { useState, useTransition } from "react";
import { ChevronRight, RefreshCw, Loader2 } from "lucide-react";

export function LogDrawer({
  label,
  fetchLog,
}: {
  label: string;
  fetchLog: () => Promise<string[]>;
}) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<string[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const load = () => {
    setErr(null);
    start(async () => {
      try {
        setLines(await fetchLog());
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
  };

  const toggle = () => {
    if (!open && lines === null) load();
    setOpen(!open);
  };

  return (
    <>
      <button
        type="button"
        onClick={toggle}
        title={`${open ? "hide" : "show"} ${label}`}
        aria-label={`${open ? "hide" : "show"} ${label}`}
        className="inline-flex h-7 w-7 items-center justify-center rounded border border-zinc-700 hover:bg-zinc-800"
      >
        <ChevronRight
          className={`h-4 w-4 transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open && (
        <div className="col-span-full mt-2 rounded border border-zinc-800 bg-black/50">
          <div className="flex items-center justify-between border-b border-zinc-800 px-2 py-1 text-[11px] text-zinc-500">
            <span>{label}</span>
            <button
              type="button"
              onClick={load}
              disabled={pending}
              title="refresh"
              aria-label="refresh"
              className="inline-flex h-6 w-6 items-center justify-center rounded hover:bg-zinc-800 disabled:opacity-50"
            >
              {pending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
          <pre className="max-h-80 overflow-auto px-3 py-2 text-[11px] leading-snug text-zinc-300">
            {err ? (
              <span className="text-red-400">{err}</span>
            ) : lines === null ? (
              <span className="text-zinc-500">loading…</span>
            ) : lines.length === 0 ? (
              <span className="text-zinc-500">(empty)</span>
            ) : (
              lines.join("\n")
            )}
          </pre>
        </div>
      )}
    </>
  );
}
