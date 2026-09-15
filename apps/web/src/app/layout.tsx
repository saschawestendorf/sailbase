import type { Metadata } from "next";
import { Fraunces, Geist_Mono, Inter } from "next/font/google";
import Link from "next/link";

import SiteHeader from "@/components/SiteHeader";
import Burgee from "@/components/ui/Burgee";

import "./globals.css";

// Inter trägt die Oberfläche: dichte Zahlen, ruhige Formulare.
const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
// Fraunces setzt die Überschriften und Preise. Optische Größe an, WONK aus:
// die Kontrastwirkung einer Buchschrift ohne die verspielten Formen.
const fraunces = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
  axes: ["SOFT", "WONK", "opsz"],
});
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sailbase – Yachtcharter mit dynamischen Preisen",
  description:
    "Segelyachten in der Ostsee flexibel chartern: freie Zeiträume statt starrer Wochen, " +
    "dynamische Preise und ein Boot, das zur Crew passt.",
};

const FOOTER_LINKS: { title: string; items: { href: string; label: string }[] }[] = [
  {
    title: "Chartern",
    items: [
      { href: "/search", label: "Boote finden" },
      { href: "/booking", label: "Meine Buchung" },
    ],
  },
  {
    title: "Vercharterer",
    items: [
      { href: "/charterer", label: "Meine Flotte" },
      { href: "/charterer/boats/new", label: "Boot einstellen" },
    ],
  },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="de"
      className={`${inter.variable} ${fraunces.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-paper-grain">
        <SiteHeader />

        <main className="flex-1">{children}</main>

        <footer className="mt-20 bg-sea text-[#e9f1f4]">
          <div className="mx-auto w-full max-w-6xl px-4 py-14">
            <div className="grid gap-10 sm:grid-cols-[1.4fr_1fr_1fr]">
              <div>
                <div className="flex items-center gap-2.5">
                  <Burgee className="h-7 w-7 text-[#45cfc4]" />
                  <span className="display text-xl tracking-tight">Sailbase</span>
                </div>
                <p className="mt-4 max-w-sm text-sm leading-relaxed text-[#9db3bd]">
                  Sailbase macht aus einem Boot einen dynamisch buchbaren Vermögenswert:
                  Preisoptimierung, Zahlung und operative Abwicklung in einem Portal.
                </p>
              </div>

              {FOOTER_LINKS.map((group) => (
                <div key={group.title}>
                  <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-[#74909c]">
                    {group.title}
                  </p>
                  <ul className="mt-3 space-y-2 text-sm">
                    {group.items.map((item) => (
                      <li key={item.href}>
                        <Link href={item.href} className="text-[#cfe0e6] hover:text-white">
                          {item.label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            <div className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-6 text-xs text-[#74909c]">
              <p>Ostsee · Flensburg bis Rügen</p>
              <p>Demo-Umgebung. Preise und Verfügbarkeiten stammen aus Testdaten.</p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
