"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TOOLS } from "@/lib/tools";

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="nav">
      <div className="nav-inner">
        <Link href="/" className="brand">
          <span className="brand-mark">◍</span>
          Cella
        </Link>
        <div className="nav-links">
          <Link
            href="/about"
            className={`nav-link ${pathname === "/about" ? "active" : ""}`}
          >
            About
          </Link>
          {TOOLS.map((t) => {
            const active = pathname === t.href;
            return (
              <Link
                key={t.slug}
                href={t.href}
                className={`nav-link ${active ? "active" : ""}`}
              >
                {t.name}
                {t.status === "planned" && <span className="soon">soon</span>}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
