import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sailbase – Yachtcharter mit dynamischen Preisen",
  description:
    "Segelyachten in der Ostsee flexibel chartern: freie Zeiträume statt starrer Wochen, " +
    "dynamische Preise und ein Boot, das zur Crew passt.",
};

function Anchor() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="4.5" r="2" />
      <path d="M12 6.5V21M5 12H3a9 9 0 0 0 18 0h-2M7.5 9.5h9" strokeLinecap="round" />
    </svg>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="de" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-brand">
              <Anchor />
              <span className="text-lg">Sailbase</span>
            </Link>
            <nav className="flex items-center gap-1 text-sm sm:gap-3">
              <Link href="/search" className="rounded-lg px-2 py-1.5 hover:bg-surface-muted sm:px-3">
                Boote finden
              </Link>
              <Link href="/booking" className="rounded-lg px-2 py-1.5 hover:bg-surface-muted sm:px-3">
                Meine Buchung
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-line bg-surface">
          <div className="mx-auto grid w-full max-w-6xl gap-4 px-4 py-8 text-sm text-muted sm:grid-cols-2">
            <p className="max-w-sm">
              Sailbase macht aus einem Boot einen dynamisch buchbaren Vermögenswert: Preisoptimierung,
              Zahlung und operative Abwicklung in einem Portal.
            </p>
            <p className="sm:text-right">
              Demo-Umgebung. Preise und Verfügbarkeiten stammen aus Testdaten.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
