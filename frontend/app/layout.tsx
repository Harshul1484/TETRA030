import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

// figmaSans is proprietary. Inter carries the same variable-weight range and
// takes the negative display tracking well.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Vedha",
  description:
    "Audits university syllabi against live job market data and proposes adoptable modifications.",
};

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/graph", label: "Skill graph" },
  { href: "/about", label: "How it works" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} min-h-screen antialiased`}>
        {/* A floating pill rather than a full-width bar. Detaching the nav
            from the page edge lets the warm canvas run behind it, which is
            what keeps the page feeling like paper rather than an app chrome. */}
        <header className="sticky top-0 z-20 px-4 pt-4 sm:px-6 sm:pt-6">
          <div className="mx-auto flex max-w-[1180px] flex-wrap items-center gap-x-8 gap-y-3 rounded-[var(--radius-full)] border border-[var(--color-hairline)] bg-[var(--color-surface)]/95 px-6 py-3.5 backdrop-blur sm:px-8">
            <Link href="/" className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="inline-block h-4 w-4 rounded-[5px]"
                style={{ backgroundColor: "var(--color-block-periwinkle)" }}
              />
              <span className="text-[17px] font-semibold tracking-tight">
                Vedha
              </span>
            </Link>

            <nav className="flex gap-6 text-[15px] sm:gap-7">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <span className="tabular ml-auto hidden text-[13px] text-[var(--color-ink-mute)] sm:inline-block">
              TETRA030
            </span>
          </div>
        </header>

        <main className="mx-auto max-w-[1180px] px-6 py-12">{children}</main>

        <footer className="mt-24 border-t border-[var(--color-hairline)]">
          <div className="mx-auto max-w-[1180px] px-6 py-10">
            <p className="caption text-[var(--color-ink-mute)]">
              TETRA030 | TetraTHON 2026, Track D | Job market data from
              Arbeitnow and Remotive
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
