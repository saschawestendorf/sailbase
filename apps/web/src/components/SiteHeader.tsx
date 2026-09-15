import Link from "next/link";

import { logout } from "@/app/actions/auth";
import Burgee from "@/components/ui/Burgee";
import { getSession, ROLE_LABELS } from "@/lib/session";

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

/** Unterstreichung wächst aus der Mitte: ruhiger als ein Farbwechsel und
 *  verschiebt das Layout nicht. */
function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="group relative shrink-0 px-3 py-2 text-sm text-muted transition-colors hover:text-foreground"
    >
      {label}
      <span className="absolute inset-x-3 -bottom-0.5 h-px origin-center scale-x-0 bg-accent transition-transform duration-200 group-hover:scale-x-100" />
    </Link>
  );
}

export default async function SiteHeader() {
  const session = await getSession();
  const links = session ? (NAV_BY_ROLE[session.role] ?? GUEST_NAV) : GUEST_NAV;

  return (
    <header className="sticky top-0 z-30 border-b border-line/80 bg-surface/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3.5">
        <Link href="/" className="group flex items-center gap-2.5 text-brand">
          <Burgee className="h-6 w-6 text-accent transition-transform duration-300 group-hover:-translate-y-0.5" />
          <span className="display text-[1.35rem] leading-none tracking-tight">Sailbase</span>
        </Link>

        <nav className="flex items-center gap-1">
          {/* Auf breiten Geräten in der Kopfzeile, auf schmalen in der Leiste
              darunter – ausgeblendet wird nichts, sonst wäre etwa "Meine
              Buchung" am Telefon nicht mehr erreichbar. */}
          <div className="hidden items-center gap-1 sm:flex">
            {links.map((link) => (
              <NavLink key={link.href} href={link.href} label={link.label} />
            ))}
          </div>

          {session ? (
            <form action={logout} className="ml-2 flex items-center gap-2.5">
              <span className="hidden items-center gap-2 text-xs text-muted lg:flex">
                <span className="font-medium text-foreground">
                  {session.full_name || session.email}
                </span>
                <span className="chip chip-accent">{ROLE_LABELS[session.role]}</span>
              </span>
              <button type="submit" className="btn-quiet">
                Abmelden
              </button>
            </form>
          ) : (
            <div className="ml-2 flex items-center gap-2">
              <Link href="/login" className="btn-quiet hidden sm:inline-flex">
                Anmelden
              </Link>
              <Link href="/search" className="btn-primary">
                Boot finden
              </Link>
            </div>
          )}
        </nav>
      </div>

      <div className="border-t border-line/70 sm:hidden">
        <div className="mx-auto flex w-full max-w-6xl items-center gap-1 overflow-x-auto px-3 py-1.5">
          {links.map((link) => (
            <NavLink key={link.href} href={link.href} label={link.label} />
          ))}
          {session ? null : <NavLink href="/login" label="Anmelden" />}
        </div>
      </div>
    </header>
  );
}
