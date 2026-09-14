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
    <div className="mx-auto w-full max-w-md px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Anmelden</h1>
      <p className="mt-2 text-sm text-muted">
        Für Vercharterer und Servicepartner. Als Gast brauchst du für deine Buchung kein Konto.
      </p>
      <div className="mt-6">
        <LoginForm next={next} />
      </div>
      <div className="card mt-6 p-4 text-sm text-muted">
        <p className="font-medium text-foreground">Demo-Zugänge</p>
        <p className="mt-1">Vercharterer: charter@ostsee-yachting.example · charter123</p>
        <p>Servicepartner: service@hafenhelfer.example · partner123</p>
      </div>
    </div>
  );
}
