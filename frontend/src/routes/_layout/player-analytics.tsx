import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  ChevronDown,
  ChevronUp,
  Info,
  Link2,
  Loader2,
  Trophy,
  UsersRound,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { WeekSelector } from "@/components/Common/WeekSelector"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useLeague } from "@/contexts/LeagueContext"
import { PlayerAnalyticsService, type PlayerStatMeta } from "@/lib/footballApi"

interface PlayerSearch {
  league?: string
  week?: number
  stat?: string
  category?: string
}

export const Route = createFileRoute("/_layout/player-analytics")({
  component: PlayerAnalytics,
  validateSearch: (search: Record<string, unknown>): PlayerSearch => ({
    league: typeof search.league === "string" ? search.league : undefined,
    week:
      search.week != null && Number.isFinite(Number(search.week))
        ? Number(search.week)
        : undefined,
    stat: typeof search.stat === "string" ? search.stat : undefined,
    category: typeof search.category === "string" ? search.category : undefined,
  }),
  head: () => ({
    meta: [{ title: "Player Analytics - Los Football" }],
  }),
})

// Keys handled explicitly by the renderer (not shown as generic numeric stats).
const META_KEYS = new Set([
  "roster_id",
  "player_id",
  "display_name",
  "avatar",
  "player_name",
  "position",
  "team",
  "classification",
  "flag",
  "injured",
])

const FLAG_VARIANTS: Record<string, string> = {
  "Buy Low": "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  "Sell High": "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  Rookie: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  Breakout: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  "Boom/Bust": "bg-rose-500/15 text-rose-600 dark:text-rose-400",
  Consistent: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  Balanced: "bg-slate-500/15 text-slate-600 dark:text-slate-400",
}

interface InjuredPlayer {
  player_name: string
  position: string
  status: string
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

function PlayerRow({
  row,
  index,
}: {
  row: Record<string, unknown>
  index: number
}) {
  // Player-level rows carry a player_name; roster-level rows fall back to the
  // owner display_name + avatar.
  const playerName = row.player_name as string | undefined
  const ownerName = (row.display_name as string) ?? `Team ${row.roster_id}`
  const primary = playerName ?? ownerName
  const avatar = row.avatar as string | null | undefined
  const position = row.position as string | undefined
  const team = row.team as string | null | undefined
  const flag =
    (row.flag as string) ?? (row.classification as string) ?? undefined
  const injured = Array.isArray(row.injured)
    ? (row.injured as InjuredPlayer[])
    : undefined

  const numericFields = Object.entries(row).filter(
    ([k, v]) => !META_KEYS.has(k) && typeof v === "number",
  )

  return (
    <div className="flex flex-col gap-2 rounded-lg px-3 py-2.5 transition-colors hover:bg-accent/65 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3 min-w-0">
        <span className="w-6 shrink-0 text-sm font-black tabular-nums text-muted-foreground">
          {index + 1}
        </span>
        {playerName ? (
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary ring-1 ring-border/80 text-[11px] font-black">
            {position ?? "?"}
          </div>
        ) : avatar ? (
          <img
            src={`https://sleepercdn.com/avatars/thumbs/${avatar}`}
            alt={primary}
            className="h-8 w-8 shrink-0 rounded-full ring-1 ring-border/80"
          />
        ) : (
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary ring-1 ring-border/80">
            <Trophy className="w-4 h-4 text-muted-foreground" />
          </div>
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <span className="truncate font-semibold">{primary}</span>
            {flag && (
              <Badge
                variant="secondary"
                className={`shrink-0 text-[10px] ${FLAG_VARIANTS[flag] ?? ""}`}
              >
                {flag}
              </Badge>
            )}
          </div>
          {playerName && (
            <p className="truncate text-xs text-muted-foreground">
              {[team, position].filter(Boolean).join(" · ")}
              {ownerName ? ` — ${ownerName}` : ""}
            </p>
          )}
          {injured && injured.length > 0 && (
            <p className="truncate text-xs text-muted-foreground">
              {injured.map((p) => `${p.player_name} (${p.status})`).join(", ")}
            </p>
          )}
        </div>
      </div>
      <div className="flex shrink-0 gap-4 pl-9 sm:ml-4 sm:pl-0">
        {numericFields.slice(0, 3).map(([key, value]) => (
          <div key={key} className="text-right">
            <p className="text-xs font-semibold capitalize text-muted-foreground">
              {key.replace(/_/g, " ")}
            </p>
            <p className="text-sm font-black tabular-nums">
              {formatNumber(value as number)}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

function PlayerStatCard({
  meta,
  leagueId,
  week,
  defaultExpanded = false,
  onShare,
}: {
  meta: PlayerStatMeta
  leagueId: string
  week?: number
  defaultExpanded?: boolean
  onShare: () => void
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  useEffect(() => {
    if (defaultExpanded) setExpanded(true)
  }, [defaultExpanded])

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["player-analytics-stat", meta.key, leagueId, week],
    queryFn: () => PlayerAnalyticsService.getStat(meta.key, leagueId, week),
    enabled: !!leagueId && expanded,
    retry: false,
  })

  return (
    <Card
      id={`player-stat-${meta.key}`}
      className="scroll-mt-24 overflow-hidden transition-[background-color,box-shadow,transform] hover:-translate-y-0.5 hover:bg-card"
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <Badge variant="secondary" className="text-[11px] uppercase">
                {meta.category}
              </Badge>
            </div>
            <CardTitle className="text-base font-black">{meta.title}</CardTitle>
            <CardDescription className="text-xs mt-1">
              {meta.description}
            </CardDescription>
          </div>
          <div className="flex shrink-0 items-center">
            <Button
              variant="ghost"
              size="icon"
              onClick={onShare}
              className="h-8 w-8"
              aria-label="Copy shareable link"
            >
              <Link2 className="h-4 w-4 text-muted-foreground" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setExpanded((v) => !v)}
              disabled={!leagueId}
              className="h-8 w-8"
              aria-label={expanded ? "Collapse" : "Expand"}
            >
              {expanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="pt-0">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {isError && (
            <div className="flex items-center gap-2 rounded-md bg-secondary/70 p-3 text-sm text-foreground">
              <Info className="h-4 w-4 shrink-0 text-destructive" />
              <span>{(error as Error)?.message ?? "Failed to load stat"}</span>
            </div>
          )}
          {data && Array.isArray(data) && data.length > 0 && (
            <div className="divide-y divide-border/60">
              {(data as Record<string, unknown>[])
                .slice(0, 15)
                .map((row, i) => (
                  <PlayerRow
                    key={
                      (row.player_id as string) ??
                      (row.roster_id as string) ??
                      i
                    }
                    row={row}
                    index={i}
                  />
                ))}
            </div>
          )}
          {data && Array.isArray(data) && data.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No data available yet
            </p>
          )}
        </CardContent>
      )}
    </Card>
  )
}

function PlayerAnalytics() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { activeLeagueId, addLeague, effectiveWeek, setSelectedWeek } =
    useLeague()

  const [inputLeagueId, setInputLeagueId] = useState("")
  const [filterCategory, setFilterCategory] = useState<string>(
    search.category ?? "all",
  )
  const syncedRef = useRef(false)

  useEffect(() => {
    if (syncedRef.current) return
    syncedRef.current = true
    if (search.league && search.league !== activeLeagueId) {
      addLeague(search.league)
    }
    if (typeof search.week === "number") {
      setSelectedWeek(search.week)
    }
  }, [search.league, search.week, activeLeagueId, addLeague, setSelectedWeek])

  useEffect(() => {
    if (!search.stat) return
    const el = document.getElementById(`player-stat-${search.stat}`)
    el?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, [search.stat])

  const {
    data: statsMeta,
    isLoading: metaLoading,
    isError: metaError,
    refetch: refetchMeta,
  } = useQuery({
    queryKey: ["player-analytics-meta"],
    queryFn: PlayerAnalyticsService.getStatsMeta,
    retry: false,
  })

  const categories = statsMeta
    ? ["all", ...new Set(statsMeta.map((s) => s.category))]
    : ["all"]

  const filteredStats = statsMeta?.filter(
    (s) => filterCategory === "all" || s.category === filterCategory,
  )

  const handleCategory = (value: string) => {
    setFilterCategory(value)
    navigate({
      search: (prev) => ({
        ...prev,
        category: value === "all" ? undefined : value,
      }),
      replace: true,
    })
  }

  const handleAddLeague = () => {
    const trimmed = inputLeagueId.trim()
    if (!trimmed) return
    addLeague(trimmed)
    setInputLeagueId("")
  }

  const shareStat = (statKey: string) => {
    const params = new URLSearchParams()
    if (activeLeagueId) params.set("league", activeLeagueId)
    params.set("week", String(effectiveWeek))
    params.set("stat", statKey)
    if (filterCategory !== "all") params.set("category", filterCategory)
    const url = `${window.location.origin}/player-analytics?${params.toString()}`
    navigator.clipboard
      .writeText(url)
      .then(() => toast.success("Shareable link copied to clipboard"))
      .catch(() => toast.error("Could not copy link"))
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap rounded-2xl border border-border/70 bg-card/75 p-6 shadow-[0_24px_80px_-52px_rgb(0_0_0/0.9)]">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
            Analytics Suite
          </p>
          <h1 className="text-3xl font-black tracking-tight flex items-center gap-2">
            <UsersRound className="h-7 w-7 text-primary" />
            Player Analytics
          </h1>
          <p className="text-muted-foreground">
            Player-level production, usage, value, and availability from the
            Sleeper API
          </p>
        </div>
      </div>

      {/* League configuration — only when no league is active yet */}
      {!activeLeagueId && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-bold uppercase tracking-[0.14em] text-muted-foreground">
              League Configuration
            </CardTitle>
            <CardDescription className="text-xs">
              Enter your Sleeper League ID to load player analytics. Find it in
              the Sleeper app under League → Settings → League ID.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <Label htmlFor="league-id" className="text-xs mb-1 block">
                  Sleeper League ID
                </Label>
                <Input
                  id="league-id"
                  placeholder="e.g. 123456789012345678"
                  value={inputLeagueId}
                  onChange={(e) => setInputLeagueId(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddLeague()}
                  className="h-8 text-sm"
                />
              </div>
              <Button size="sm" onClick={handleAddLeague} className="h-8">
                Load League
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Week selector */}
      {activeLeagueId && <WeekSelector />}

      {/* Category filter */}
      <div className="flex items-center gap-3 flex-wrap rounded-xl border border-border/70 bg-card/60 p-3">
        <Label className="text-sm font-bold text-muted-foreground">
          Filter by category:
        </Label>
        <Select value={filterCategory} onValueChange={handleCategory}>
          <SelectTrigger className="w-48 h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {categories.map((cat) => (
              <SelectItem key={cat} value={cat} className="text-sm">
                {cat === "all" ? "All categories" : cat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {filteredStats && (
          <span className="text-xs font-semibold text-muted-foreground">
            {filteredStats.length} stat{filteredStats.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Stats grid */}
      {metaLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : metaError ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 gap-3 text-center">
            <Info className="h-8 w-8 text-destructive" />
            <div>
              <p className="font-medium">Unable to load player analytics</p>
              <p className="text-sm text-muted-foreground">
                Check that the backend is running and try again.
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => refetchMeta()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredStats?.map((meta) => (
            <PlayerStatCard
              key={meta.key}
              meta={meta}
              leagueId={activeLeagueId}
              week={effectiveWeek}
              defaultExpanded={search.stat === meta.key}
              onShare={() => shareStat(meta.key)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
