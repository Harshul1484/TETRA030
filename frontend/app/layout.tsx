import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CurricuAlign AI",
  description:
    "Audits university syllabi against live job market data and proposes adoptable modifications.",
};

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/graph", label: "Skill Graph" },
  { href: "/about", label: "How It Works" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-slate-950 text-slate-200 antialiased`}
      >
        <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-6 py-4">
            <Link href="/" className="flex items-baseline gap-3">
              <span className="text-lg font-semibold tracking-tight text-slate-100">
                CurricuAlign AI
              </span>
              <span className="hidden text-xs text-slate-500 lg:inline">
                Dynamic Syllabus and Industry Skill-Gap Synchronizer
              </span>
            </Link>
            <nav className="flex gap-6 text-sm">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-slate-400 transition-colors hover:text-slate-100"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>

        <footer className="mt-16 border-t border-slate-800 px-6 py-6">
          <p className="mx-auto max-w-7xl text-xs leading-relaxed text-slate-500">
            TETRA030 | TetraTHON 2026, Track D | Job market data from Arbeitnow
            and Remotive
          </p>
        </footer>
      </body>
    </html>
  );
}
