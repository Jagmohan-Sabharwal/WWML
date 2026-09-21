import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { Navigation } from "./components/navigation";
import { AppearanceProvider } from "./components/appearance";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "WWML · Documentary workspace", template: "%s · WWML" },
  description: "Discover reusable assets and organize documentary production.",
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <AppearanceProvider>
          <a
            href="#main"
            className="sr-only z-50 rounded bg-surface p-4 text-ink focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
          >
            Skip to content
          </a>
          <div className="min-h-screen md:grid md:grid-cols-[232px_minmax(0,1fr)]">
            <aside className="bg-[#182c26] px-5 py-6 md:sticky md:top-0 md:flex md:h-screen md:flex-col md:px-6 md:py-9">
              <Link
                href="/dashboard"
                aria-label="WWML dashboard"
                className="mb-6 flex items-center gap-3 text-white md:mb-12"
              >
                <span className="flex size-9 items-center justify-center rounded-lg bg-[#d8e8be] text-xl font-bold text-[#182c26]">
                  W
                </span>
                <span className="text-xl font-semibold tracking-widest">
                  WWML
                </span>
              </Link>
              <p className="mb-4 hidden text-[10px] font-medium uppercase tracking-[.2em] text-[#96aca0] md:block">
                Production workspace
              </p>
              <Navigation />
              <div className="mt-auto hidden border-t border-white/15 pt-6 text-xs leading-6 text-[#a9bdb1] md:block">
                <p className="font-medium text-[#d8e8be]">
                  Make more from what you have.
                </p>
                <p className="mt-2">
                  Your footage. Your stories.
                  <br />
                  One shared library.
                </p>
              </div>
            </aside>
            <div className="min-w-0">
              <div className="flex items-center justify-between border-b border-line px-6 py-5 text-xs text-muted sm:px-10">
                <span>
                  WWML <span className="mx-2 text-muted/50">/</span> Documentary
                  studio
                </span>
                <span className="rounded-full border border-line px-3 py-1.5">
                  Workspace
                </span>
              </div>
              <main
                id="main"
                tabIndex={-1}
                className="mx-auto max-w-[1440px] px-5 py-8 sm:px-10 sm:py-10 lg:px-12"
              >
                {children}
              </main>
              <footer className="mx-5 border-t border-line py-5 text-xs text-muted sm:mx-10 lg:mx-12">
                WWML · Built for documentary production
              </footer>
            </div>
          </div>
        </AppearanceProvider>
      </body>
    </html>
  );
}
