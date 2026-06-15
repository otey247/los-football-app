import { Link, useRouterState } from "@tanstack/react-router"
import {
  BarChart3,
  BookOpen,
  Home,
  type LucideIcon,
  Swords,
  User,
} from "lucide-react"

import { cn } from "@/lib/utils"

interface Tab {
  label: string
  to: string
  icon: LucideIcon
  // Match these path prefixes for the active state.
  match: string[]
}

// Matchups maps to Insights, which surfaces matchup previews and storylines.
const TABS: Tab[] = [
  { label: "Home", to: "/", icon: Home, match: ["/"] },
  {
    label: "Stats",
    to: "/fantasy-stats",
    icon: BarChart3,
    match: ["/fantasy-stats"],
  },
  { label: "Matchups", to: "/insights", icon: Swords, match: ["/insights"] },
  { label: "Blog", to: "/blog", icon: BookOpen, match: ["/blog"] },
  { label: "Profile", to: "/settings", icon: User, match: ["/settings"] },
]

export function MobileTabBar() {
  const router = useRouterState()
  const pathname = router.location.pathname

  const isActive = (tab: Tab) =>
    tab.to === "/"
      ? pathname === "/"
      : tab.match.some((m) => pathname.startsWith(m))

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border/70 bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden"
    >
      <ul className="flex items-stretch justify-around">
        {TABS.map((tab) => {
          const active = isActive(tab)
          return (
            <li key={tab.to} className="flex-1">
              <Link
                to={tab.to}
                className={cn(
                  "flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition-colors",
                  active
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <tab.icon className="h-5 w-5" />
                <span>{tab.label}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
