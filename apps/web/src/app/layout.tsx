import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import SiteHeader from "@/components/SiteHeader";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sailbase – Yachtcharter mit dynamischen Preisen",
  description:
    "Segelyachten in der Ostsee flexibel chartern: freie Zeiträume statt starrer Wochen, " +
    "dynamische Preise und ein Boot, das zur Crew passt.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="de" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <SiteHeader />

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
