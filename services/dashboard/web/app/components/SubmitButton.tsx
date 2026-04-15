"use client";

import { useFormStatus } from "react-dom";
import { Loader2 } from "lucide-react";

type Variant = "icon" | "text" | "primary";

export function SubmitButton({
  children,
  title,
  ariaLabel,
  name,
  value,
  variant = "icon",
  tone = "default",
}: {
  children: React.ReactNode;
  title?: string;
  ariaLabel?: string;
  name?: string;
  value?: string;
  variant?: Variant;
  tone?: "default" | "danger";
}) {
  const { pending } = useFormStatus();
  const base =
    variant === "primary"
      ? "rounded border border-zinc-700 bg-zinc-800 px-3 py-1 hover:bg-zinc-700"
      : variant === "text"
        ? "rounded border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-800"
        : "inline-flex h-7 w-7 items-center justify-center rounded border border-zinc-700 hover:bg-zinc-800";
  const toneCls =
    tone === "danger" ? " hover:border-red-700 hover:text-red-400" : "";
  return (
    <button
      type="submit"
      disabled={pending}
      aria-busy={pending}
      aria-label={ariaLabel ?? title}
      title={title}
      name={name}
      value={value}
      className={`${base}${toneCls} disabled:cursor-wait disabled:opacity-60`}
    >
      {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : children}
    </button>
  );
}
