import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "./ui-icon";

export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-5">
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-[.18em] text-accent">
          {eyebrow}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
          {description}
        </p>
      </div>
      {children}
    </header>
  );
}
export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-line bg-surface ${className}`}
    >
      {children}
    </section>
  );
}
export function ActionLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="inline-flex items-center justify-center gap-3 rounded-lg bg-ink px-4 py-3 text-sm font-medium text-surface hover:opacity-85"
    >
      {children}
      <Icon name="arrow" />
    </Link>
  );
}
export function EmptyState({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="px-6 py-14 text-center">
      <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-xl bg-soft text-accent">
        <Icon name="film" className="size-7" />
      </div>
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted">
        {description}
      </p>
      {children && <div className="mt-6">{children}</div>}
    </div>
  );
}
export function Unavailable({
  message = "We couldn’t load your library. Check platform status and try again.",
}: {
  message?: string;
}) {
  return (
    <div role="alert" className="rounded-xl border border-line bg-surface p-8">
      <h2 className="text-lg font-semibold">Temporarily unavailable</h2>
      <p className="mt-2 text-sm text-muted">{message}</p>
      <Link
        href="/settings"
        className="mt-4 inline-block text-sm font-semibold text-accent underline underline-offset-4"
      >
        View platform status
      </Link>
    </div>
  );
}
