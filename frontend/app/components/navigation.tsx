"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./ui-icon";

const links: { href: string; label: string; icon: IconName }[] = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { href: "/assets", label: "Assets", icon: "assets" },
  { href: "/productions", label: "Productions", icon: "productions" },
  { href: "/settings", label: "Settings", icon: "settings" },
];
export function Navigation() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main navigation"
      className="grid grid-cols-2 gap-1 md:grid-cols-1"
    >
      {links.map(({ href, label, icon }) => {
        const active = pathname === href || pathname.startsWith(href + "/");
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition-colors ${active ? "bg-[#d8e8be] text-[#182c2a]" : "text-[#bdcbc3] hover:bg-white/10 hover:text-white"}`}
          >
            <Icon name={icon} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
