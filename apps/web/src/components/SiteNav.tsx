"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function SiteNav() {
  const path = usePathname();
  const item = (href: string, label: string) => (
    <Link href={href} aria-current={path === href ? "page" : undefined} className="navlink">
      {label}
    </Link>
  );
  return (
    <header className="sitenav">
      <Link href="/" className="brand" aria-label="Crewbie home">
        <span className="brand-dot" aria-hidden /> Crewbie
      </Link>
      <nav aria-label="Primary">
        {item("/", "Campus Pulse")}
        {item("/arena", "Mission Control")}
      </nav>
      <span className="pill pill-synth" title="All bundled data is fictional">Synthetic data</span>
    </header>
  );
}
