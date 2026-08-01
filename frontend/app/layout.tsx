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
  title: "CurricuAlign AI",
  description:
    "Audits university syllabi against live job market data and proposes adoptable modifications.",
};

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/graph", label: "Skill graph" },
  { href: "/about", label: "How it works" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} min-h-screen antialiased`}>
        <header className="sticky top-0 z-20 border-b border-[var(--color-hairline)] bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-[1180px] flex-wrap items-center gap-x-10 gap-y-3 px-6 py-5">
            <Link href="/" className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="inline-block h-4 w-4 rounded-[5px]"
                style={{ backgroundColor: "var(--color-block-lilac)" }}
              />
              <span className="text-[17px] font-semibold tracking-tight">
                CurricuAlign
              </span>
            </Link>

            <nav className="flex gap-7 text-[15px]">
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

            <span
              className="micro-cap ml-auto hidden rounded-[var(--radius-full)] px-2.5 py-1 sm:inline-block"
              style={{ backgroundColor: "var(--color-block-lime)" }}
            >
              TETRA030
            </span>
          </div>
        </header>

        <main className="mx-auto max-w-[1180px] px-6 py-14">{children}</main>

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
