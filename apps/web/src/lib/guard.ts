import { redirect } from "next/navigation";

import { getSession, type Session } from "@/lib/session";
import { readToken } from "@/lib/session";

/** Pages behind a role: sends the visitor to the login and back afterwards. */
export async function requireRole(
  role: Session["role"],
  returnTo: string,
): Promise<{ session: Session; token: string }> {
  const session = await getSession();
  if (!session) redirect(`/login?next=${encodeURIComponent(returnTo)}`);
  if (session.role !== role && session.role !== "admin") redirect("/");
  const token = await readToken();
  if (!token) redirect(`/login?next=${encodeURIComponent(returnTo)}`);
  return { session, token };
}
