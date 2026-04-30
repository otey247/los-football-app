import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  BarChart3,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  Trophy,
} from "lucide-react"
import { useState } from "react"

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
import { SleeperService, type SleeperStatMeta } from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/fantasy-stats")({
  component: FantasyStats,
  head: () => ({
    meta: [{ title: "Fantasy Stats - Los Football" }],
  }),
})

interface StatRowProps {
  row: Record<string, unknown>
  index: number
}

function StatRow({ row, index }: StatRowProps) {
  const displayName = (row.display_name as string) ?? `Team ${row.roster_id}`
  const avatar = row.avatar as string | null

  const numericFields = Object.entries(row).filter(
    ([k, v]) =>
      k !== "roster_id" &&
      k !== "display_name" &&
      k !== "avatar" &&
      k !== "player_id" &&
      k !== "instances" &&
      k !== "picks" &&
      typeof v === "number",
  )

  return (
    <div className="flex items-center justify-between rounded-lg px-3 py-2.5 transition-colors hover:bg-accent/65">
      <div className="flex items-center gap-3 min-w-0">
        <span className="w-6 shrink-0 text-sm font-black tabular-nums text-muted-foreground">
          {index + 1}
        </span>
        <div className="flex items-center gap-2 min-w-0">
          {avatar ? (
            <img
              src={`https://sleepercdn.com/avatars/thumbs/${avatar}`}
              alt={displayName}
              className="h-8 w-8 shrink-0 rounded-full ring-1 ring-border/80"
            />
          ) : (
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary ring-1 ring-border/80">
              <Trophy className="w-4 h-4 text-muted-foreground" />
            </div>
          )}
          <span className="truncate font-semibold">{displayName}</span>
        </div>
      </div>
      <div className="flex gap-4 shrink-0 ml-4">
        {numericFields.slice(0, 3).map(([key, value]) => (
          <div key={key} className="text-right">
            <p className="text-xs font-semibold capitalize text-muted-foreground">
              {key.replace(/_/g, " ")}
            </p>
            <p className="text-sm font-black tabular-nums">
              {typeof value === "number"
                ? Number.isInteger(value)
                  ? value
                  : value.toFixed(2)
                : String(value)}
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
}

function StatCard({ meta, leagueId, week }: StatCardProps) {
  const [expanded, setExpanded] = useState(false)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["sleeper-stat", meta.key, leagueId, week],
    queryFn: () => SleeperService.getStat(meta.key, leagueId, week),
    enabled: !!leagueId && expanded,
    retry: false,
  })

  return (
    <Card className="overflow-hidden transition-[background-color,box-shadow,transform] hover:-translate-y-0.5 hover:bg-card">
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
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded((v) => !v)}
            disabled={!leagueId}
            className="shrink-0"
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
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
                .slice(0, 12)
                .map((row, i) => (
                  <StatRow
                    key={(row.roster_id as string) ?? i}
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

function FantasyStats() {
  const [leagueId, setLeagueId] = useState(
    () => localStorage.getItem("sleeper_league_id") ?? "",
  )
  const [inputLeagueId, setInputLeagueId] = useState(leagueId)
  const [filterCategory, setFilterCategory] = useState<string>("all")

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

  const handleSaveLeague = () => {
    const trimmed = inputLeagueId.trim()
    setLeagueId(trimmed)
    localStorage.setItem("sleeper_league_id", trimmed)
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
            <BarChart3 className="h-7 w-7 text-primary" />
            Fantasy Stats
          </h1>
          <p className="text-muted-foreground">
            Top 25 advanced stats powered by the Sleeper API
          </p>
        </div>
      </div>

      {/* League ID configuration */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-bold uppercase tracking-[0.14em] text-muted-foreground">
            League Configuration
          </CardTitle>
          <CardDescription className="text-xs">
            Enter your Sleeper League ID to load stats. Find it in the Sleeper
            app under League → Settings → League ID.
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
                onKeyDown={(e) => e.key === "Enter" && handleSaveLeague()}
                className="h-8 text-sm"
              />
            </div>
            <Button size="sm" onClick={handleSaveLeague} className="h-8">
              Load League
            </Button>
          </div>
          {leagueId && (
             <p className="mt-3 text-xs font-medium text-muted-foreground">
               League ID set:{" "}
               <code className="font-mono text-foreground">{leagueId}</code>
             </p>
           )}
           {!leagueId && (
             <p className="mt-3 text-xs font-medium text-muted-foreground">
               Enter a league ID above then click "Load League" to expand any
               stat card
             </p>
           )}
        </CardContent>
      </Card>

      {/* Category filter */}
      <div className="flex items-center gap-3 flex-wrap rounded-xl border border-border/70 bg-card/60 p-3">
        <Label className="text-sm font-bold text-muted-foreground">
          Filter by category:
        </Label>
        <Select value={filterCategory} onValueChange={setFilterCategory}>
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
              <p className="font-medium">Unable to load fantasy stat cards</p>
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
            <StatCard key={meta.key} meta={meta} leagueId={leagueId} />
          ))}
        </div>
      )}
    </div>
  )
}
