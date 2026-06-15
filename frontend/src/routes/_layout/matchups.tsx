import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  Activity,
  ArrowLeftRight,
  Crown,
  Dices,
  Info,
  ListChecks,
  Loader2,
  Percent,
  Radio,
  Swords,
  Target,
  Trophy,
} from "lucide-react"
import { useState } from "react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useLeague } from "@/contexts/LeagueContext"
import {
  type ChampionshipResponse,
  type ClinchTeam,
  type LineupOptionsResponse,
  type LiveWinProbTeam,
  MatchupService,
  type PlayoffOddsTeam,
  type SeasonSimTeam,
  SleeperService,
  type WhatIfResponse,
  type WinProbTeam,
} from "@/lib/footballApi"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/matchups")({
  component: Matchups,
  head: () => ({
    meta: [{ title: "Matchups - Los Football" }],
  }),
})

// ---- Shared bits -----------------------------------------------------------

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}

function ErrorState({ message }: { message?: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-secondary/70 p-3 text-sm">
      <Info className="h-4 w-4 shrink-0 text-destructive" />
      <span>{message ?? "Failed to load"}</span>
    </div>
  )
}

function Avatar({ avatar, name }: { avatar?: string | null; name: string }) {
  return avatar ? (
    <img
      src={`https://sleepercdn.com/avatars/thumbs/${avatar}`}
      alt={name}
      className="h-7 w-7 shrink-0 rounded-full ring-1 ring-border/80"
    />
  ) : (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary ring-1 ring-border/80">
      <Trophy className="h-3.5 w-3.5 text-muted-foreground" />
    </div>
  )
}

function ProbBar({ pct }: { pct: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
      <div
        className="h-full rounded-full bg-primary transition-all"
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  )
}

// ---- #59 / #60 Win probability ---------------------------------------------

function WinProbCard({
  m,
  live,
}: {
  m: { matchup: (WinProbTeam | LiveWinProbTeam)[] }
  live?: boolean
}) {
  const [a, b] = m.matchup
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border/70 bg-card/60 p-4">
      {[a, b].map((t) => (
        <div key={t.roster_id} className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Avatar avatar={t.avatar} name={t.display_name} />
              <span className="truncate font-semibold">{t.display_name}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0 text-right tabular-nums">
              <span className="text-xs text-muted-foreground">
                {"current_points" in t
                  ? `${t.current_points} → ${t.projected_points}`
                  : `${t.projected_points} proj`}
              </span>
              <span className="w-12 font-black">{t.win_probability}%</span>
            </div>
          </div>
          <ProbBar pct={t.win_probability} />
        </div>
      ))}
      {live && "starters_yet_to_play" in a && (
        <p className="text-[11px] text-muted-foreground">
          {a.starters_yet_to_play + (b as typeof a).starters_yet_to_play}{" "}
          starters yet to play
        </p>
      )}
    </div>
  )
}

function WinProbabilityTab({ leagueId, week }: TabProps) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["matchup-winprob", leagueId, week],
    queryFn: () => MatchupService.getWinProbability(leagueId, week),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  if (data.matchups.length === 0)
    return (
      <p className="py-6 text-sm text-muted-foreground">
        No matchups scheduled for week {data.week} yet.
      </p>
    )
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-black">Week {data.week} · Pre-Game Odds</h3>
      <div className="grid gap-3 md:grid-cols-2">
        {data.matchups.map((m, i) => (
          <WinProbCard key={i} m={m} />
        ))}
      </div>
    </div>
  )
}

function LiveWinProbabilityTab({ leagueId, week }: TabProps) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["matchup-live", leagueId, week],
    queryFn: () => MatchupService.getLiveWinProbability(leagueId, week),
    enabled: !!leagueId,
    retry: false,
    refetchInterval: 60_000,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-black">Week {data.week} · Live Odds</h3>
        <Badge variant="secondary" className="text-[11px]">
          <Radio className="mr-1 h-3 w-3 animate-pulse" /> auto-refresh
        </Badge>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {data.matchups.map((m, i) => (
          <WinProbCard key={i} m={m} live />
        ))}
      </div>
    </div>
  )
}

// ---- #61 Projection accuracy -----------------------------------------------

function ProjectionAccuracyTab({ leagueId, week }: TabProps) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["matchup-accuracy", leagueId, week],
    queryFn: () => MatchupService.getProjectionAccuracy(leagueId, week),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  const o = data.overall
  const stats = [
    {
      label: "Pick accuracy",
      value: o.pick_accuracy != null ? `${o.pick_accuracy}%` : "—",
    },
    { label: "Mean abs error", value: o.mae != null ? o.mae : "—" },
    { label: "RMSE", value: o.rmse != null ? o.rmse : "—" },
    { label: "Bias", value: o.bias != null ? o.bias : "—" },
  ]
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-black">Projection Accuracy</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-lg border border-border/70 bg-card/60 p-3"
          >
            <p className="text-xs font-semibold text-muted-foreground">
              {s.label}
            </p>
            <p className="text-2xl font-black tabular-nums">{s.value}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Based on {o.scored_samples} team-weeks and {o.picks_total} matchups.
        Projections use each team's running average from prior weeks.
      </p>
      {data.by_week.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-sm font-bold">Weekly mean absolute error</p>
          {data.by_week.map((w) => {
            const max = Math.max(...data.by_week.map((x) => x.mae), 1)
            return (
              <div key={w.week} className="flex items-center gap-2 text-xs">
                <span className="w-12 shrink-0 text-muted-foreground">
                  Wk {w.week}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${(w.mae / max) * 100}%` }}
                  />
                </div>
                <span className="w-12 shrink-0 text-right tabular-nums font-semibold">
                  {w.mae}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ---- #62 What-if simulator -------------------------------------------------

function WhatIfTab({ leagueId, week }: TabProps) {
  const [rosterId, setRosterId] = useState<number | null>(null)
  const [swapOut, setSwapOut] = useState<string>("")
  const [swapIn, setSwapIn] = useState<string>("")
  const [result, setResult] = useState<WhatIfResponse | null>(null)

  const { data: league } = useQuery({
    queryKey: ["matchup-leagueinfo", leagueId],
    queryFn: () => SleeperService.getLeagueInfo(leagueId),
    enabled: !!leagueId,
    retry: false,
  })

  const rosterOptions = (() => {
    if (!league) return [] as { roster_id: number; name: string }[]
    const users = new Map(
      league.users.map((u) => [
        String(u.user_id),
        u as Record<string, unknown>,
      ]),
    )
    return league.rosters.map((r) => {
      const owner = users.get(String((r as Record<string, unknown>).owner_id))
      const meta = owner?.metadata as Record<string, unknown> | undefined
      const name =
        (meta?.team_name as string) ||
        (owner?.display_name as string) ||
        `Team ${(r as Record<string, unknown>).roster_id}`
      return {
        roster_id: Number((r as Record<string, unknown>).roster_id),
        name,
      }
    })
  })()

  const { data: lineup } = useQuery<LineupOptionsResponse>({
    queryKey: ["matchup-lineup", leagueId, rosterId, week],
    queryFn: () =>
      MatchupService.getLineupOptions(rosterId as number, leagueId, week),
    enabled: !!leagueId && rosterId != null,
    retry: false,
  })

  const run = useMutation({
    mutationFn: () =>
      MatchupService.postWhatIf({
        leagueId,
        rosterId: rosterId as number,
        week,
        swapOut,
        swapIn,
      }),
    onSuccess: (res) => setResult(res),
  })

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-black">What-If Simulator</h3>
      <p className="text-sm text-muted-foreground">
        Swap a starter for a bench player to see the projected point and
        win-probability impact.
      </p>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-muted-foreground">
            Team
          </span>
          <Select
            value={rosterId != null ? String(rosterId) : ""}
            onValueChange={(v) => {
              setRosterId(Number(v))
              setSwapOut("")
              setSwapIn("")
              setResult(null)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select a team" />
            </SelectTrigger>
            <SelectContent>
              {rosterOptions.map((r) => (
                <SelectItem key={r.roster_id} value={String(r.roster_id)}>
                  {r.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-muted-foreground">
            Bench starter
          </span>
          <Select value={swapOut} onValueChange={setSwapOut} disabled={!lineup}>
            <SelectTrigger>
              <SelectValue placeholder="Starter out" />
            </SelectTrigger>
            <SelectContent>
              {(lineup?.starters ?? []).map((p) => (
                <SelectItem key={p.player_id} value={p.player_id}>
                  {p.name} ({p.projected_points})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-muted-foreground">
            Start instead
          </span>
          <Select value={swapIn} onValueChange={setSwapIn} disabled={!lineup}>
            <SelectTrigger>
              <SelectValue placeholder="Bench in" />
            </SelectTrigger>
            <SelectContent>
              {(lineup?.bench ?? []).map((p) => (
                <SelectItem key={p.player_id} value={p.player_id}>
                  {p.name} ({p.projected_points})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Button
        className="self-start"
        disabled={!swapOut || !swapIn || run.isPending}
        onClick={() => run.mutate()}
      >
        {run.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          "Simulate swap"
        )}
      </Button>

      {run.isError && <ErrorState message={(run.error as Error)?.message} />}

      {result && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-border/70 bg-card/60 p-3">
            <p className="text-xs font-semibold text-muted-foreground">
              Projected total
            </p>
            <p className="text-xl font-black tabular-nums">
              {result.current_projected_total} → {result.new_projected_total}
            </p>
            <p
              className={cn(
                "text-sm font-bold tabular-nums",
                result.delta >= 0 ? "text-emerald-500" : "text-destructive",
              )}
            >
              {result.delta >= 0 ? "+" : ""}
              {result.delta} pts
            </p>
          </div>
          {result.win_probability_after != null && (
            <div className="rounded-lg border border-border/70 bg-card/60 p-3">
              <p className="text-xs font-semibold text-muted-foreground">
                Win probability
              </p>
              <p className="text-xl font-black tabular-nums">
                {result.win_probability_before}% →{" "}
                {result.win_probability_after}%
              </p>
              <p
                className={cn(
                  "text-sm font-bold tabular-nums",
                  (result.win_probability_delta ?? 0) >= 0
                    ? "text-emerald-500"
                    : "text-destructive",
                )}
              >
                {(result.win_probability_delta ?? 0) >= 0 ? "+" : ""}
                {result.win_probability_delta} pts
              </p>
            </div>
          )}
          {result.opponent && (
            <div className="rounded-lg border border-border/70 bg-card/60 p-3">
              <p className="text-xs font-semibold text-muted-foreground">
                Opponent
              </p>
              <p className="truncate text-base font-black">
                {result.opponent.display_name}
              </p>
              <p className="text-sm tabular-nums text-muted-foreground">
                {result.opponent.projected_points} proj
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---- #63 Clinch scenarios --------------------------------------------------

function StatusBadge({ status }: { status: ClinchTeam["status"] }) {
  const map = {
    clinched: { label: "Clinched", cls: "bg-emerald-500/15 text-emerald-500" },
    eliminated: {
      label: "Eliminated",
      cls: "bg-destructive/15 text-destructive",
    },
    in_contention: {
      label: "In the hunt",
      cls: "bg-amber-500/15 text-amber-500",
    },
  } as const
  const m = map[status]
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide",
        m.cls,
      )}
    >
      {m.label}
    </span>
  )
}

function ClinchTab({ leagueId, week }: TabProps) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["matchup-clinch", leagueId, week],
    queryFn: () => MatchupService.getClinchScenarios(leagueId, week),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-lg font-black">
        Clinch & Elimination · Top {data.playoff_teams} make the playoffs
      </h3>
      <div className="flex flex-col gap-1.5">
        {data.teams.map((t, i) => (
          <div
            key={t.roster_id}
            className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/60 px-3 py-2"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-5 shrink-0 text-sm font-black tabular-nums text-muted-foreground">
                {i + 1}
              </span>
              <Avatar avatar={t.avatar} name={t.display_name} />
              <span className="truncate font-semibold">{t.display_name}</span>
            </div>
            <div className="flex items-center gap-4 shrink-0 text-right text-sm tabular-nums">
              <span className="hidden sm:inline text-muted-foreground">
                {t.wins}-{t.losses}
                {t.ties ? `-${t.ties}` : ""}
              </span>
              <span className="hidden md:inline text-muted-foreground">
                max {t.max_possible_wins}W
              </span>
              {t.clinch_magic_number != null && (
                <span className="text-xs text-muted-foreground">
                  magic {t.clinch_magic_number}
                </span>
              )}
              <StatusBadge status={t.status} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---- #64 Season simulation -------------------------------------------------

function SeasonSimTab({ leagueId, week }: TabProps) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["matchup-sim", leagueId, week],
    queryFn: () => MatchupService.getSeasonSimulation(leagueId, week),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  const rows: SeasonSimTeam[] = data.teams
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-lg font-black">
        Projected Final Standings
        <span className="ml-2 text-sm font-medium text-muted-foreground">
          {data.simulations.toLocaleString()} simulations
        </span>
      </h3>
      <div className="flex flex-col gap-1.5">
        {rows.map((t, i) => (
          <div
            key={t.roster_id}
            className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/60 px-3 py-2"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-5 shrink-0 text-sm font-black tabular-nums text-muted-foreground">
                {i + 1}
              </span>
              <Avatar avatar={t.avatar} name={t.display_name} />
              <span className="truncate font-semibold">{t.display_name}</span>
            </div>
            <div className="flex items-center gap-4 shrink-0 text-right text-sm tabular-nums">
              <span className="text-muted-foreground">
                {t.projected_wins}W proj
              </span>
              <span className="hidden sm:inline text-muted-foreground">
                {t.projected_points} pts
              </span>
              <span className="w-14 font-black">{t.playoff_probability}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---- #65 Playoff odds ------------------------------------------------------

function Sparkline({ trend }: { trend: PlayoffOddsTeam["trend"] }) {
  if (trend.length < 2) return null
  const w = 80
  const h = 20
  const pts = trend.map((p, i) => {
    const x = (i / (trend.length - 1)) * w
    const y = h - (p.playoff_probability / 100) * h
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return (
    <svg width={w} height={h} className="shrink-0" role="img">
      <title>Weekly playoff-odds trend</title>
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        className="text-primary"
      />
    </svg>
  )
}

function PlayoffOddsTab({ leagueId, week }: TabProps) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["matchup-playoff", leagueId, week],
    queryFn: () => MatchupService.getPlayoffOdds(leagueId, week),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-lg font-black">Playoff Odds</h3>
      <div className="flex flex-col gap-1.5">
        {data.teams.map((t) => (
          <div
            key={t.roster_id}
            className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/60 px-3 py-2"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Avatar avatar={t.avatar} name={t.display_name} />
              <span className="truncate font-semibold">{t.display_name}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <Sparkline trend={t.trend} />
              <div className="w-28">
                <ProbBar pct={t.playoff_probability} />
              </div>
              <span className="w-14 text-right font-black tabular-nums">
                {t.playoff_probability}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---- #66 Championship odds & bracket ---------------------------------------

function ChampionshipTab({ leagueId, week }: TabProps) {
  const { data, isLoading, isError, error } = useQuery<ChampionshipResponse>({
    queryKey: ["matchup-champ", leagueId, week],
    queryFn: () => MatchupService.getChampionshipOdds(leagueId, week),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <h3 className="text-lg font-black">Championship Odds</h3>
        <div className="flex flex-col gap-1.5">
          {data.teams
            .filter((t) => t.playoff_probability > 0)
            .map((t) => (
              <div
                key={t.roster_id}
                className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-card/60 px-3 py-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Avatar avatar={t.avatar} name={t.display_name} />
                  <span className="truncate font-semibold">
                    {t.display_name}
                  </span>
                </div>
                <div className="flex items-center gap-4 shrink-0 text-right text-sm tabular-nums">
                  <span className="hidden sm:inline text-muted-foreground">
                    finals {t.finals_probability}%
                  </span>
                  <span className="flex w-16 items-center justify-end gap-1 font-black">
                    <Crown className="h-3.5 w-3.5 text-amber-500" />
                    {t.championship_probability}%
                  </span>
                </div>
              </div>
            ))}
        </div>
      </div>

      {data.projected_bracket.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-lg font-black">Projected Bracket</h3>
          <div className="grid gap-3 md:grid-cols-3">
            {data.projected_bracket.map((round) => (
              <div key={round.round} className="flex flex-col gap-2">
                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                  {round.name}
                </p>
                {round.games.map((g, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-border/70 bg-card/60 p-2 text-sm"
                  >
                    {[g.high_seed, g.low_seed].map((s) => (
                      <div
                        key={s.roster_id}
                        className={cn(
                          "flex items-center justify-between gap-2",
                          g.favorite_roster_id === s.roster_id &&
                            "font-black text-primary",
                        )}
                      >
                        <span className="truncate">
                          <span className="text-muted-foreground">
                            #{s.seed}{" "}
                          </span>
                          {s.display_name}
                        </span>
                        {g.favorite_roster_id === s.roster_id && (
                          <span className="shrink-0 text-xs">
                            {g.favorite_win_probability}%
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Page shell ------------------------------------------------------------

interface TabProps {
  leagueId: string
  week?: number
}

function Matchups() {
  const { activeLeagueId, hasLeague, selectedWeek } = useLeague()
  const week = selectedWeek ?? undefined

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4 flex-wrap rounded-2xl border border-border/70 bg-card/75 p-6 shadow-[0_24px_80px_-52px_rgb(0_0_0/0.9)]">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
            Analytics
          </p>
          <h1 className="text-3xl font-black tracking-tight flex items-center gap-2">
            <Swords className="h-7 w-7 text-primary" />
            Matchups & Win Probability
          </h1>
          <p className="text-muted-foreground">
            Win-probability models, what-if swaps, clinch scenarios, and Monte
            Carlo playoff projections.
          </p>
        </div>
      </div>

      {!hasLeague ? (
        <Card>
          <CardHeader>
            <CardTitle>No league selected</CardTitle>
            <CardDescription>
              Add a Sleeper league from the top nav to unlock matchup analytics.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center justify-center py-8 gap-2 text-center">
            <Info className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Win probability and playoff odds unlock once a league is loaded.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <WeekSelector />
          <Card>
            <CardContent className="pt-6">
              <Tabs defaultValue="winprob">
                <TabsList className="flex flex-wrap h-auto">
                  <TabsTrigger value="winprob">
                    <Percent className="mr-1 h-4 w-4" /> Win Prob
                  </TabsTrigger>
                  <TabsTrigger value="live">
                    <Activity className="mr-1 h-4 w-4" /> Live
                  </TabsTrigger>
                  <TabsTrigger value="accuracy">
                    <Target className="mr-1 h-4 w-4" /> Accuracy
                  </TabsTrigger>
                  <TabsTrigger value="whatif">
                    <ArrowLeftRight className="mr-1 h-4 w-4" /> What-If
                  </TabsTrigger>
                  <TabsTrigger value="clinch">
                    <ListChecks className="mr-1 h-4 w-4" /> Clinch
                  </TabsTrigger>
                  <TabsTrigger value="sim">
                    <Dices className="mr-1 h-4 w-4" /> Season Sim
                  </TabsTrigger>
                  <TabsTrigger value="playoff">
                    <Percent className="mr-1 h-4 w-4" /> Playoff Odds
                  </TabsTrigger>
                  <TabsTrigger value="champ">
                    <Crown className="mr-1 h-4 w-4" /> Championship
                  </TabsTrigger>
                </TabsList>
                <div className="mt-6">
                  <TabsContent value="winprob">
                    <WinProbabilityTab leagueId={activeLeagueId} week={week} />
                  </TabsContent>
                  <TabsContent value="live">
                    <LiveWinProbabilityTab
                      leagueId={activeLeagueId}
                      week={week}
                    />
                  </TabsContent>
                  <TabsContent value="accuracy">
                    <ProjectionAccuracyTab
                      leagueId={activeLeagueId}
                      week={week}
                    />
                  </TabsContent>
                  <TabsContent value="whatif">
                    <WhatIfTab leagueId={activeLeagueId} week={week} />
                  </TabsContent>
                  <TabsContent value="clinch">
                    <ClinchTab leagueId={activeLeagueId} week={week} />
                  </TabsContent>
                  <TabsContent value="sim">
                    <SeasonSimTab leagueId={activeLeagueId} week={week} />
                  </TabsContent>
                  <TabsContent value="playoff">
                    <PlayoffOddsTab leagueId={activeLeagueId} week={week} />
                  </TabsContent>
                  <TabsContent value="champ">
                    <ChampionshipTab leagueId={activeLeagueId} week={week} />
                  </TabsContent>
                </div>
              </Tabs>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
