import { redirect } from "next/navigation";

import { LoginForm } from "@/components/AuthForms";
import { getSession } from "@/lib/session";

export const dynamic = "force-dynamic";
export const metadata = { title: "Anmelden – Sailbase" };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function LoginPage(props: PageProps<"/login">) {
  const session = await getSession();
  const next = first((await props.searchParams).next);
  if (session) redirect(next ?? "/search");
  return (
    <div className="mx-auto w-full max-w-md px-4 py-16">
      <p className="eyebrow">Sailbase</p>
      <h1 className="mt-3 text-3xl">Anmelden</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        Für Vercharterer und Servicepartner. Als Gast brauchst du für deine Buchung kein Konto.
      </p>
      <div className="mt-7">
        <LoginForm next={next} />
      </div>
      <div className="mt-6 rounded-xl border border-dashed border-line-strong px-4 py-3.5 text-sm text-muted">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-faint">Demo-Zugänge</p>
        <p className="mt-2">Vercharterer: charter@ostsee-yachting.example · charter123</p>
        <p>Servicepartner: service@hafenhelfer.example · partner123</p>
      </div>
    </div>
  );
}
