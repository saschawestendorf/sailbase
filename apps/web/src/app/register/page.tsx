import { redirect } from "next/navigation";

import { RegisterForm } from "@/components/AuthForms";
import { getSession } from "@/lib/session";

export const dynamic = "force-dynamic";
export const metadata = { title: "Registrieren – Sailbase" };

export default async function RegisterPage() {
  if (await getSession()) redirect("/search");
  return (
    <div className="mx-auto w-full max-w-md px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Konto anlegen</h1>
      <p className="mt-2 text-sm text-muted">
        Als Vercharterer stellst du dein Boot ein, legst den Preisrahmen fest und übergibst den
        Rest dem Algorithmus.
      </p>
      <div className="mt-6">
        <RegisterForm />
      </div>
    </div>
  );
}
