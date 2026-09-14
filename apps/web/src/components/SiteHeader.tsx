import Link from "next/link";

import { logout } from "@/app/actions/auth";
import { getSession, ROLE_LABELS } from "@/lib/session";

function Anchor() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      className="h-6 w-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <circle cx="12" cy="4.5" r="2" />
      <path d="M12 6.5V21M5 12H3a9 9 0 0 0 18 0h-2M7.5 9.5h9" strokeLinecap="round" />
    </svg>
  );
}

const NAV_BY_ROLE: Record<string, { href: string; label: string }[]> = {
  charterer: [
    { href: "/search", label: "Boote finden" },
    { href: "/charterer", label: "Meine Flotte" },
    { href: "/charterer/boats/new", label: "Boot einstellen" },
  ],
  partner: [
    { href: "/search", label: "Boote finden" },
    { href: "/partner", label: "Meine Aufträge" },
  ],
};

const GUEST_NAV = [
  { href: "/search", label: "Boote finden" },
  { href: "/booking", label: "Meine Buchung" },
];

export default async function SiteHeader() {
  const session = await getSession();
  const links = session ? (NAV_BY_ROLE[session.role] ?? GUEST_NAV) : GUEST_NAV;

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-brand">
          <Anchor />
          <span className="text-lg">Sailbase</span>
        </Link>

        <nav className="flex items-center gap-1 text-sm">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-lg px-2 py-1.5 hover:bg-surface-muted sm:px-3"
            >
              {link.label}
            </Link>
          ))}
          {session ? (
            <form action={logout} className="ml-1 flex items-center gap-2">
              <span className="hidden text-xs text-muted sm:inline">
                {session.full_name || session.email}
                <span className="ml-1 chip">{ROLE_LABELS[session.role]}</span>
              </span>
              <button type="submit" className="btn-ghost">
                Abmelden
              </button>
            </form>
          ) : (
            <Link href="/login" className="btn-ghost ml-1">
              Anmelden
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
