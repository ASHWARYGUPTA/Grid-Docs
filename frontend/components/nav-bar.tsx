"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TierBadge } from "@/components/tier-badge";

const ROUTES = [
  { href: "/live", label: "Live" },
  { href: "/planned", label: "Planned" },
  { href: "/governance", label: "Governance" },
  { href: "/analytics", label: "Analytics" },
  { href: "/report", label: "Report" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b flex items-center justify-between px-4 h-14 shrink-0">
      <nav className="flex items-center gap-1">
        <span className="font-semibold mr-4">Grid Unlocked</span>
        {ROUTES.map((route) => (
          <Link
            key={route.href}
            href={route.href}
            className={`px-3 py-1.5 rounded-md text-sm ${
              pathname?.startsWith(route.href)
                ? "bg-secondary font-medium"
                : "text-muted-foreground hover:bg-secondary/50"
            }`}
          >
            {route.label}
          </Link>
        ))}
      </nav>
      <TierBadge />
    </header>
  );
}
