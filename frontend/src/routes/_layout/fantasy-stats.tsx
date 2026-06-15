import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  BarChart3,
  ChevronDown,
  ChevronUp,
  Download,
  Link2,
  Star,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { AnimatedNumber } from "@/components/Common/AnimatedNumber"
import { DensityToggle } from "@/components/Common/DensityToggle"
import { EmptyState } from "@/components/Common/EmptyState"
import {
  StatCardSkeleton,
  StatRowsSkeleton,
} from "@/components/Common/StatCardSkeleton"
import { TeamAvatar } from "@/components/Common/TeamAvatar"
import { WeekSelector } from "@/components/Common/WeekSelector"
import { StatChart } from "@/components/fantasy/StatCharts"
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
import { usePreferences } from "@/contexts/PreferencesContext"
import {
  ReportingService,
  SleeperService,
  type SleeperStatMeta,
} from "@/lib/footballApi"
import { teamColorFromSeed } from "@/lib/teamColor"
import { cn } from "@/lib/utils"

interface FantasySearch {
  league?: string
  week?: number
  stat?: string
  category?: string
}

export const Route = createFileRoute("/_layout/fantasy-stats")({
  component: FantasyStats,
  validateSearch: (search: Record<string, unknown>): FantasySearch => ({
    league: typeof search.league === "string" ? search.league : undefined,
    week:
      search.week != null && Number.isFinite(Number(search.week))
        ? Number(search.week)
        : undefined,
    stat: typeof search.stat === "string" ? search.stat : undefined,
    category: typeof search.category === "string" ? search.category : undefined,
  }),
  head: () => ({
    meta: [{ title: "Fantasy Stats - Los Football" }],
  }),
})

interface StatRowProps {
  row: Record<string, unknown>
  index: number
}

/** Percentage-style fields render with a `%` suffix. */
function isPercentField(key: string): boolean {
  return /(pct|percent|probability|odds|efficiency)/.test(key)
}

function StatRow({ row, index }: StatRowProps) {
  const { density } = usePreferences()
  const compact = density === "compact"
  const displayName = (row.display_name as string) ?? `Team ${row.roster_id}`
  const avatar = row.avatar as string | null
  // Stable per-franchise accent color (item 9).
  const tc = teamColorFromSeed(
    (row.roster_id as string | number) ?? displayName,
  )
  const playerName = row.player_name as string | undefined
  const subtitle = [playerName, row.position as string | undefined]
    .filter(Boolean)
    .join(" · ")

  const numericFields = Object.entries(row).filter(
    ([k, v]) =>
      k !== "roster_id" &&
      k !== "display_name" &&
      k !== "avatar" &&
      k !== "player_id" &&
      k !== "instances" &&
      k !== "picks" &&
      k !== "weekly" &&
      typeof v === "number",
  )

  return (
    <div
      className={cn(
        "group/row relative flex items-center justify-between rounded-lg pr-3 transition-colors hover:bg-accent/65",
        compact ? "py-1.5 pl-4" : "py-2.5 pl-4",
      )}
    >
      {/* Team-color accent bar */}
      <span
        aria-hidden="true"
        className="absolute inset-y-1.5 left-1 w-1 rounded-full opacity-70 transition-opacity group-hover/row:opacity-100"
        style={{ backgroundColor: tc.color }}
      />
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={cn(
            "grid shrink-0 place-items-center rounded-md text-xs font-black tabular-nums",
            compact ? "h-6 w-6" : "h-7 w-7",
          )}
          style={{ backgroundColor: tc.soft, color: tc.color }}
        >
          {index + 1}
        </span>
        <div className="flex min-w-0 items-center gap-2">
          <TeamAvatar
            avatar={avatar}
            name={displayName}
            seed={(row.roster_id as string | number) ?? displayName}
            className={compact ? "h-7 w-7" : "h-8 w-8"}
          />
          <div className="min-w-0">
            <span className="block truncate font-semibold">{displayName}</span>
            {subtitle && (
              <span className="block truncate text-xs text-muted-foreground">
                {subtitle}
              </span>
            )}
          </div>
        </div>
      </div>
      <div
        className={cn("flex shrink-0", compact ? "ml-3 gap-3" : "ml-4 gap-4")}
      >
        {numericFields.slice(0, 3).map(([key, value]) => (
          <div key={key} className="text-right">
            <p className="text-xs font-semibold capitalize text-muted-foreground">
              {key.replace(/_/g, " ")}
            </p>
            <p className="text-sm font-black">
              <AnimatedNumber
                value={value as number}
                suffix={isPercentField(key) ? "%" : ""}
              />
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

interface StatCardProps {
  meta: SleeperStatMeta
  leagueId: string
  week?: number
  startWeek?: number
  defaultExpanded?: boolean
  isFavorite: boolean
  onToggleFavorite: () => void
  onShare: () => void
}

function StatCard({
  meta,
  leagueId,
  week,
  startWeek,
  defaultExpanded = false,
  isFavorite,
  onToggleFavorite,
  onShare,
}: StatCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const [exporting, setExporting] = useState(false)

  // Re-open if a deep link targets this card after it has mounted.
  useEffect(() => {
    if (defaultExpanded) setExpanded(true)
  }, [defaultExpanded])

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["sleeper-stat", meta.key, leagueId, week, startWeek],
    queryFn: () => SleeperService.getStat(meta.key, leagueId, week, startWeek),
    enabled: !!leagueId && expanded,
    retry: false,
  })

  // #79 Record which stat cards managers actually open.
  useEffect(() => {
    if (expanded && leagueId) {
      ReportingService.recordUsage("card_open", meta.key, "/fantasy-stats")
    }
  }, [expanded, leagueId, meta.key])

  const handleExport = async (format: "csv" | "json") => {
    setExporting(true)
    try {
      await SleeperService.exportStat(
        meta.key,
        format,
        leagueId,
        week,
        startWeek,
      )
      ReportingService.recordUsage("export", `${meta.key}:${format}`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <Card
      id={`stat-${meta.key}`}
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
              onClick={onToggleFavorite}
              className="h-8 w-8"
              aria-label={isFavorite ? "Unpin stat card" : "Pin stat card"}
              aria-pressed={isFavorite}
            >
              <Star
                className={cn(
                  "h-4 w-4",
                  isFavorite
                    ? "fill-primary text-primary"
                    : "text-muted-foreground",
                )}
              />
            </Button>
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
          {isLoading && <StatRowsSkeleton rows={6} />}
          {isError && (
            <EmptyState
              illustration="error"
              className="py-6"
              title="Couldn't load this stat"
              description={
                (error as Error)?.message ??
                "Something went wrong fetching Sleeper data."
              }
            />
          )}
          {data && Array.isArray(data) && data.length > 0 && (
            <>
              {meta.chart && (
                <div className="mb-4">
                  <StatChart
                    chart={meta.chart}
                    rows={data as Record<string, unknown>[]}
                  />
                </div>
              )}
              <div className="divide-y divide-border/60">
                {(data as Record<string, unknown>[])
                  .slice(0, 12)
                  .map((row, i) => (
                    <StatRow
                      key={`${(row.roster_id as string) ?? (row.player_id as string) ?? "row"}-${i}`}
                      row={row}
                      index={i}
                    />
                  ))}
              </div>
              {/* #75 CSV / JSON export */}
              <div className="mt-3 flex items-center justify-end gap-2 border-t border-border/60 pt-3">
                <span className="mr-auto text-xs text-muted-foreground">
                  Export this table
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  disabled={exporting}
                  onClick={() => handleExport("csv")}
                >
                  <Download className="mr-1 h-3 w-3" /> CSV
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  disabled={exporting}
                  onClick={() => handleExport("json")}
                >
                  <Download className="mr-1 h-3 w-3" /> JSON
                </Button>
              </div>
            </>
          )}
          {data && Array.isArray(data) && data.length === 0 && (
            <EmptyState
              illustration="preseason"
              className="py-6"
              title="No data yet"
              description="This stat will populate once games are played for the selected week."
            />
          )}
        </CardContent>
      )}
    </Card>
  )
}

function FantasyStats() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const {
    activeLeagueId,
    addLeague,
    effectiveWeek,
    setSelectedWeek,
    favorites,
    isFavorite,
    toggleFavorite,
  } = useLeague()

  const [inputLeagueId, setInputLeagueId] = useState("")
  const [filterCategory, setFilterCategory] = useState<string>(
    search.category ?? "all",
  )
  // #77 Custom week-range filtering: effectiveWeek is the inclusive end, this is
  // the optional start (blank = full season to date).
  const [startWeek, setStartWeek] = useState<string>("")
  const startWeekNum = startWeek ? Number(startWeek) : undefined
  const syncedRef = useRef(false)

  useEffect(() => {
    ReportingService.recordUsage("page_view", "fantasy-stats", "/fantasy-stats")
  }, [])

  // Apply deep-link search params to global state once on entry.
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

  // Scroll a deep-linked stat card into view.
  useEffect(() => {
    if (!search.stat) return
    const el = document.getElementById(`stat-${search.stat}`)
    el?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, [search.stat])

  const {
    data: statsMeta,
    isLoading: metaLoading,
    isError: metaError,
    refetch: refetchMeta,
  } = useQuery({
    queryKey: ["sleeper-meta"],
    queryFn: SleeperService.getStatsMeta,
    retry: false,
  })

  const categories = statsMeta
    ? ["all", ...new Set(statsMeta.map((s) => s.category))]
    : ["all"]

  const filteredStats = statsMeta?.filter(
    (s) => filterCategory === "all" || s.category === filterCategory,
  )

  const pinnedStats = statsMeta?.filter((s) => favorites.includes(s.key)) ?? []

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
    const url = `${window.location.origin}/fantasy-stats?${params.toString()}`
    navigator.clipboard
      .writeText(url)
      .then(() => toast.success("Shareable link copied to clipboard"))
      .catch(() => toast.error("Could not copy link"))
  }

  const renderCard = (meta: SleeperStatMeta) => (
    <StatCard
      key={meta.key}
      meta={meta}
      leagueId={activeLeagueId}
      week={effectiveWeek}
      startWeek={startWeekNum}
      defaultExpanded={search.stat === meta.key}
      isFavorite={isFavorite(meta.key)}
      onToggleFavorite={() => toggleFavorite(meta.key)}
      onShare={() => shareStat(meta.key)}
    />
  )

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap rounded-2xl border border-border/70 bg-card/75 p-6 shadow-[0_24px_80px_-52px_rgb(0_0_0/0.9)]">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
            Analytics Suite
          </p>
          <h1 className="text-3xl font-black tracking-tight flex items-center gap-2">
            <BarChart3 className="h-7 w-7 text-primary" />
            Fantasy Stats
          </h1>
          <p className="text-muted-foreground">
            Advanced stat cards powered by the Sleeper API
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
              Enter your Sleeper League ID to load stats. Find it in the Sleeper
              app under League → Settings → League ID. You can switch leagues
              any time from the top navigation.
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

      {/* Pinned / favorites rail */}
      {activeLeagueId && pinnedStats.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Star className="h-4 w-4 fill-primary text-primary" />
            <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-muted-foreground">
              Pinned stat cards
            </h2>
            <Badge variant="secondary" className="text-[11px]">
              {pinnedStats.length}
            </Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {pinnedStats.map(renderCard)}
          </div>
        </div>
      )}

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
        <div className="ml-auto flex items-center gap-2">
          <Label className="text-sm font-bold text-muted-foreground">
            From week:
          </Label>
          <Input
            type="number"
            min={1}
            max={18}
            placeholder="1"
            value={startWeek}
            onChange={(e) => setStartWeek(e.target.value)}
            className="h-8 w-20 text-sm"
          />
          <DensityToggle />
        </div>
      </div>

      {/* Stats grid */}
      {metaLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <StatCardSkeleton key={`stat-card-skeleton-${i}`} />
          ))}
        </div>
      ) : metaError ? (
        <Card>
          <CardContent className="py-6">
            <EmptyState
              illustration="error"
              title="Unable to load fantasy stat cards"
              description="Check that the backend is running and try again."
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchMeta()}
                >
                  Retry
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : filteredStats && filteredStats.length === 0 ? (
        <Card>
          <CardContent className="py-6">
            <EmptyState
              illustration="search"
              title="No stats in this category"
              description="Try a different category to see more stat cards."
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredStats?.map(renderCard)}
        </div>
      )}
    </div>
  )
}
