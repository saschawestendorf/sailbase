import { redirect } from "next/navigation";

import { RegisterForm } from "@/components/AuthForms";
import { getSession } from "@/lib/session";

export const dynamic = "force-dynamic";
export const metadata = { title: "Registrieren – Sailbase" };

export default async function RegisterPage() {
  if (await getSession()) redirect("/search");
  return (
    <div className="mx-auto w-full max-w-md px-4 py-16">
      <p className="eyebrow">Sailbase</p>
      <h1 className="mt-3 text-3xl">Konto anlegen</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        Als Vercharterer stellst du dein Boot ein, legst den Preisrahmen fest und übergibst den
        Rest dem Algorithmus.
      </p>
      <div className="mt-7">
        <RegisterForm />
      </div>
    </div>
  );
}
