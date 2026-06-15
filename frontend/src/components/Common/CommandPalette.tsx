import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  BarChart3,
  BookOpen,
  Briefcase,
  CalendarDays,
  Home,
  type LucideIcon,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Swords,
  Trophy,
  Users,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { MAX_WEEK, useLeague } from "@/contexts/LeagueContext"
import useAuth from "@/hooks/useAuth"
import { SleeperService } from "@/lib/footballApi"
import { cn } from "@/lib/utils"

interface CommandItem {
  id: string
  label: string
  group: string
  keywords?: string
  icon: LucideIcon
  perform: () => void
}

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const {
    leagues,
    activeLeagueId,
    setActiveLeague,
    setSelectedWeek,
    currentWeek,
  } = useLeague()
  const [query, setQuery] = useState("")
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: statsMeta } = useQuery({
    queryKey: ["sleeper-meta"],
    queryFn: SleeperService.getStatsMeta,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  })

  const close = useCallback(() => onOpenChange(false), [onOpenChange])

  const items = useMemo<CommandItem[]>(() => {
    const go = (to: string, search?: Record<string, unknown>) => () => {
      navigate({ to, search })
      close()
    }

    const nav: CommandItem[] = [
      {
        id: "nav-home",
        label: "Dashboard",
        group: "Navigation",
        icon: Home,
        perform: go("/"),
      },
      {
        id: "nav-stats",
        label: "Fantasy Stats",
        group: "Navigation",
        icon: BarChart3,
        perform: go("/fantasy-stats"),
      },
      {
        id: "nav-matchups",
        label: "Matchups & Win Probability",
        group: "Navigation",
        icon: Swords,
        perform: go("/matchups"),
      },
      {
        id: "nav-insights",
        label: "Insights",
        group: "Navigation",
        icon: Sparkles,
        perform: go("/insights"),
      },
      {
        id: "nav-blog",
        label: "Blog",
        group: "Navigation",
        icon: BookOpen,
        perform: go("/blog"),
      },
      {
        id: "nav-items",
        label: "Items",
        group: "Navigation",
        icon: Briefcase,
        perform: go("/items"),
      },
      {
        id: "nav-settings",
        label: "Settings",
        group: "Navigation",
        icon: Settings,
        perform: go("/settings"),
      },
    ]
    if (user?.is_superuser) {
      nav.push({
        id: "nav-admin",
        label: "Admin",
        group: "Navigation",
        icon: Users,
        perform: go("/admin"),
      })
      nav.push({
        id: "nav-super-admin",
        label: "Super Admin",
        group: "Navigation",
        icon: ShieldCheck,
        perform: go("/super-admin"),
      })
    }

    const leagueItems: CommandItem[] = leagues
      .filter((l) => l.id !== activeLeagueId)
      .map((l) => ({
        id: `league-${l.id}`,
        label: `Switch to ${l.name || l.id}`,
        group: "Leagues",
        keywords: l.id,
        icon: Trophy,
        perform: () => {
          setActiveLeague(l.id)
          close()
        },
      }))

    const statItems: CommandItem[] = (statsMeta ?? []).map((s) => ({
      id: `stat-${s.key}`,
      label: s.title,
      group: "Stat cards",
      keywords: `${s.category} ${s.description}`,
      icon: BarChart3,
      perform: () => {
        navigate({
          to: "/fantasy-stats",
          search: {
            stat: s.key,
            ...(activeLeagueId ? { league: activeLeagueId } : {}),
          },
        })
        close()
      },
    }))

    const weekItems: CommandItem[] = Array.from(
      { length: MAX_WEEK },
      (_, i) => i + 1,
    ).map((wk) => ({
      id: `week-${wk}`,
      label: `Week ${wk}${wk === currentWeek ? " (current)" : ""}`,
      group: "Weeks",
      keywords: "week",
      icon: CalendarDays,
      perform: () => {
        setSelectedWeek(wk)
        navigate({
          to: "/fantasy-stats",
          search: {
            week: wk,
            ...(activeLeagueId ? { league: activeLeagueId } : {}),
          },
        })
        close()
      },
    }))

    return [...nav, ...leagueItems, ...statItems, ...weekItems]
  }, [
    statsMeta,
    leagues,
    activeLeagueId,
    currentWeek,
    user?.is_superuser,
    navigate,
    setActiveLeague,
    setSelectedWeek,
    close,
  ])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter((item) =>
      `${item.label} ${item.group} ${item.keywords ?? ""}`
        .toLowerCase()
        .includes(q),
    )
  }, [items, query])

  // Reset state whenever the palette opens.
  useEffect(() => {
    if (open) {
      setQuery("")
      setActiveIndex(0)
    }
  }, [open])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      filtered[activeIndex]?.perform()
    }
  }

  // Render items grouped, but keep a flat index for keyboard navigation.
  let runningIndex = -1
  const groups: Record<string, CommandItem[]> = {}
  for (const item of filtered) {
    const list = groups[item.group] ?? []
    list.push(item)
    groups[item.group] = list
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="top-[15%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl"
        onOpenAutoFocus={(e) => {
          e.preventDefault()
          inputRef.current?.focus()
        }}
      >
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">
          Jump to any team, stat card, week, or league.
        </DialogDescription>
        <div className="flex items-center gap-2 border-b border-border/70 px-3">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search stat cards, weeks, leagues, pages…"
            className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div className="max-h-[22rem] overflow-y-auto p-2">
          {filtered.length === 0 && (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              No results for "{query}"
            </p>
          )}
          {Object.entries(groups).map(([group, groupItems]) => (
            <div key={group} className="mb-1">
              <p className="px-2 py-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                {group}
              </p>
              {groupItems.map((item) => {
                runningIndex += 1
                const index = runningIndex
                const isActive = index === activeIndex
                return (
                  <button
                    type="button"
                    key={item.id}
                    onClick={() => item.perform()}
                    onMouseMove={() => setActiveIndex(index)}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left text-sm transition-colors",
                      isActive
                        ? "bg-accent text-accent-foreground"
                        : "text-foreground hover:bg-accent/60",
                    )}
                  >
                    <item.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="truncate">{item.label}</span>
                  </button>
                )
              })}
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between border-t border-border/70 px-3 py-2 text-[11px] text-muted-foreground">
          <span>↑↓ to navigate · ↵ to select</span>
          <span>esc to close</span>
        </div>
      </DialogContent>
    </Dialog>
  )
}
