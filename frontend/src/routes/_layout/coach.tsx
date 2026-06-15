import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ClipboardList,
  Info,
  LineChart,
  Loader2,
  Repeat,
  Scale,
  Sparkles,
  Swords,
  Target,
  TrendingUp,
  Vote,
} from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import {
  type CoachTeam,
  type CommitteeRow,
  RecommendationsService,
} from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/coach")({
  component: Coach,
  head: () => ({
    meta: [{ title: "Coach - Los Football" }],
  }),
})

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
      <span>{message ?? "Failed to load recommendation"}</span>
    </div>
  )
}

function NoteLine({ text }: { text: string }) {
  return (
    <p className="mt-4 flex items-start gap-1.5 text-xs text-muted-foreground">
      <Info className="mt-0.5 h-3 w-3 shrink-0" />
      {text}
    </p>
  )
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const variant =
    confidence === "high"
      ? "default"
      : confidence === "medium"
        ? "secondary"
        : "outline"
  return (
    <Badge variant={variant} className="text-[11px] capitalize">
      {confidence}
    </Badge>
  )
}

// --- Per-team feature header (team picker) ---------------------------------

function TeamPicker({
  teams,
  value,
  onChange,
}: {
  teams: CoachTeam[]
  value: number | null
  onChange: (rid: number) => void
}) {
  return (
    <Select
      value={value != null ? String(value) : undefined}
      onValueChange={(v) => onChange(Number(v))}
    >
      <SelectTrigger className="w-[220px]">
        <SelectValue placeholder="Select a team" />
      </SelectTrigger>
      <SelectContent>
        {teams.map((t) => (
          <SelectItem key={t.roster_id} value={String(t.roster_id)}>
            {t.display_name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

// --- #92 Start / Sit -------------------------------------------------------

function StartSitTab({
  leagueId,
  rosterId,
}: {
  leagueId: string
  rosterId: number | null
}) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-startsit", leagueId, rosterId],
    queryFn: () =>
      RecommendationsService.getStartSit(rosterId as number, leagueId),
    enabled: !!leagueId && rosterId != null,
    retry: false,
  })
  if (rosterId == null)
    return (
      <p className="py-4 text-sm text-muted-foreground">Pick a team above.</p>
    )
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-lg font-black">
          {data.team} · Week {data.week}
        </h3>
        <Badge variant="secondary">Projected {data.projected_total} pts</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Recommended starters
          </p>
          <div className="flex flex-col gap-1.5">
            {data.starters.map((s) => (
              <div
                key={`${s.slot}-${s.player_id}`}
                className="flex items-center justify-between rounded-md border border-border/60 bg-card/60 px-3 py-1.5 text-sm"
              >
                <span className="flex items-center gap-2">
                  <span className="w-10 text-xs font-bold text-muted-foreground">
                    {s.slot}
                  </span>
                  {s.name}
                  {s.status && (
                    <Badge variant="destructive" className="text-[10px]">
                      {s.status}
                    </Badge>
                  )}
                </span>
                <span className="font-mono font-semibold">{s.proj}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Bench
          </p>
          <div className="flex flex-col gap-1.5">
            {data.bench.length === 0 && (
              <p className="text-sm text-muted-foreground">No bench players.</p>
            )}
            {data.bench.map((b) => (
              <div
                key={b.player_id}
                className="flex items-center justify-between rounded-md border border-border/40 px-3 py-1.5 text-sm text-muted-foreground"
              >
                <span className="flex items-center gap-2">
                  {b.name}
                  <span className="text-xs">{b.position}</span>
                  {b.status && (
                    <Badge variant="destructive" className="text-[10px]">
                      {b.status}
                    </Badge>
                  )}
                </span>
                <span className="font-mono">{b.proj}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {data.calls.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Closest calls
          </p>
          <div className="flex flex-col gap-1.5">
            {data.calls.map((c, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-2 rounded-md bg-secondary/40 px-3 py-2 text-sm"
              >
                <span>
                  Start <strong>{c.start}</strong> ({c.start_proj}) over{" "}
                  <strong>{c.sit}</strong> ({c.sit_proj}) at {c.slot}
                </span>
                <span className="flex items-center gap-2 whitespace-nowrap">
                  <span className="font-mono text-xs">+{c.delta}</span>
                  <ConfidenceBadge confidence={c.confidence} />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      <NoteLine text={data.note} />
    </div>
  )
}

// --- #93 Waivers -----------------------------------------------------------

function WaiversTab({
  leagueId,
  rosterId,
}: {
  leagueId: string
  rosterId: number | null
}) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-waivers", leagueId, rosterId],
    queryFn: () =>
      RecommendationsService.getWaivers(rosterId as number, leagueId),
    enabled: !!leagueId && rosterId != null,
    retry: false,
  })
  if (rosterId == null)
    return (
      <p className="py-4 text-sm text-muted-foreground">Pick a team above.</p>
    )
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 flex-wrap">
        <h3 className="text-lg font-black">{data.team}</h3>
        {data.needs.map((n) => (
          <Badge key={n.position} variant="outline">
            Need: {n.position}
          </Badge>
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        {data.suggestions.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No available trending adds right now.
          </p>
        )}
        {data.suggestions.map((s) => (
          <div
            key={s.player_id}
            className="flex items-center justify-between gap-2 rounded-md border border-border/60 bg-card/60 px-3 py-2 text-sm"
          >
            <span className="flex items-center gap-2">
              <strong>{s.name}</strong>
              <span className="text-xs text-muted-foreground">
                {s.position}
                {s.team ? ` · ${s.team}` : ""}
              </span>
              {s.fills_need && (
                <Badge variant="default" className="text-[10px]">
                  fills need
                </Badge>
              )}
              {s.status && (
                <Badge variant="destructive" className="text-[10px]">
                  {s.status}
                </Badge>
              )}
            </span>
            <span className="flex items-center gap-3 whitespace-nowrap text-xs">
              <span className="text-muted-foreground">
                {s.trending_adds.toLocaleString()} adds
              </span>
              <span className="font-mono">{s.recent_ppg} ppg</span>
            </span>
          </div>
        ))}
      </div>
      {data.drop_candidates.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Drop candidates
          </p>
          <div className="flex flex-wrap gap-2">
            {data.drop_candidates.map((d) => (
              <Badge key={d.player_id} variant="secondary">
                {d.name} ({d.recent_ppg})
              </Badge>
            ))}
          </div>
        </div>
      )}
      <NoteLine text={data.note} />
    </div>
  )
}

// --- #94 Trade targets -----------------------------------------------------

function TradesTab({
  leagueId,
  rosterId,
}: {
  leagueId: string
  rosterId: number | null
}) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-trades", leagueId, rosterId],
    queryFn: () =>
      RecommendationsService.getTradeTargets(rosterId as number, leagueId),
    enabled: !!leagueId && rosterId != null,
    retry: false,
  })
  if (rosterId == null)
    return (
      <p className="py-4 text-sm text-muted-foreground">Pick a team above.</p>
    )
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 flex-wrap">
        <h3 className="text-lg font-black">{data.team}</h3>
        {data.needs.map((n) => (
          <Badge key={n} variant="outline">
            Need: {n}
          </Badge>
        ))}
        {data.surplus.map((n) => (
          <Badge key={n} variant="secondary">
            Surplus: {n}
          </Badge>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {data.suggestions.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No clear trade fits found right now.
          </p>
        )}
        {data.suggestions.map((s, i) => (
          <div
            key={i}
            className="rounded-md border border-border/60 bg-card/60 px-3 py-2 text-sm"
          >
            <p className="font-semibold">{s.partner}</p>
            <p className="text-muted-foreground">
              Acquire <strong>{s.target_player}</strong> ({s.acquire_position},{" "}
              {s.target_ppg} ppg)
              {s.offer_player ? (
                <>
                  {" "}
                  · offer <strong>{s.offer_player}</strong> ({s.offer_position},{" "}
                  {s.offer_ppg} ppg)
                </>
              ) : null}
            </p>
          </div>
        ))}
      </div>
      <NoteLine text={data.note} />
    </div>
  )
}

// --- #95 Lineup nudges -----------------------------------------------------

function NudgesTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-nudges", leagueId],
    queryFn: () => RecommendationsService.getLineupNudges(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  if (data.nudges.length === 0)
    return (
      <p className="py-4 text-sm text-muted-foreground">
        Every lineup looks optimized — no nudges to send.
      </p>
    )
  return (
    <div className="flex flex-col gap-3">
      {data.nudges.map((n) => (
        <div
          key={n.roster_id}
          className="rounded-lg border border-border/70 bg-card/60 p-3"
        >
          <p className="font-black">{n.team}</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
            {n.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        </div>
      ))}
      <NoteLine text={data.note} />
    </div>
  )
}

// --- #96 Rest-of-season ----------------------------------------------------

function RosTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-ros", leagueId],
    queryFn: () => RecommendationsService.getRestOfSeason(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-3">
      {data.teams.map((t) => (
        <div
          key={t.roster_id}
          className="rounded-lg border border-border/70 bg-card/60 p-3"
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <p className="font-black">{t.team}</p>
            <div className="flex items-center gap-2 text-xs">
              <Badge variant="secondary">
                Proj {t.projected_final_wins} wins
              </Badge>
              <Badge
                variant={
                  t.playoff_probability_pct >= 50 ? "default" : "outline"
                }
              >
                {t.playoff_probability_pct}% playoffs
              </Badge>
            </div>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t.remaining_games} games left · SOS {t.strength_of_schedule} (
            {t.sos_vs_league >= 0 ? "+" : ""}
            {t.sos_vs_league} vs league)
          </p>
          {t.swing_matchups.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {t.swing_matchups.map((g) => (
                <Badge key={g.week} variant="outline" className="text-[11px]">
                  Wk {g.week} vs {g.opponent} ({g.win_probability}%)
                </Badge>
              ))}
            </div>
          )}
        </div>
      ))}
      <NoteLine text={data.note} />
    </div>
  )
}

// --- #97 Must-win ----------------------------------------------------------

function MustWinTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-mustwin", leagueId],
    queryFn: () => RecommendationsService.getMustWin(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  if (data.flags.length === 0)
    return (
      <p className="py-4 text-sm text-muted-foreground">
        No high-leverage games detected this week.
      </p>
    )
  return (
    <div className="flex flex-col gap-3">
      {data.flags.map((f) => (
        <div
          key={f.roster_id}
          className="flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-card/60 p-3"
        >
          <div>
            <p className="font-black flex items-center gap-2">
              {f.team}
              <Badge
                variant={f.level === "must-win" ? "destructive" : "secondary"}
                className="capitalize"
              >
                {f.level}
              </Badge>
            </p>
            <p className="text-xs text-muted-foreground">
              Week {f.week} vs {f.opponent}
            </p>
          </div>
          <div className="text-right text-xs">
            <p className="font-mono text-base font-bold">{f.swing_pct}%</p>
            <p className="text-muted-foreground">playoff swing</p>
          </div>
        </div>
      ))}
      <NoteLine text={data.note} />
    </div>
  )
}

// --- #98 Regression --------------------------------------------------------

function RegressionTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-regression", leagueId],
    queryFn: () => RecommendationsService.getRegression(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  if (data.warnings.length === 0)
    return (
      <p className="py-4 text-sm text-muted-foreground">
        No teams are notably over- or under-performing their scoring.
      </p>
    )
  return (
    <div className="flex flex-col gap-3">
      {data.warnings.map((w) => (
        <div
          key={w.roster_id}
          className="flex items-start gap-3 rounded-lg border border-border/70 bg-card/60 p-3"
        >
          <span className="text-2xl leading-none">{w.emoji}</span>
          <div>
            <p className="font-black capitalize">
              {w.team} · {w.type}
            </p>
            <p className="text-sm text-muted-foreground">{w.detail}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {w.actual_wins} actual vs {w.expected_wins} expected wins ·
              all-play {w.all_play_win_pct}%
            </p>
          </div>
        </div>
      ))}
      <NoteLine text={data.note} />
    </div>
  )
}

// --- #99 Rivalries ---------------------------------------------------------

function RivalriesTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-rivalries", leagueId],
    queryFn: () => RecommendationsService.getRivalries(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      {data.trash_talk && (
        <div className="rounded-lg border border-border/70 bg-secondary/40 p-4">
          <p className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            <Sparkles className="h-3 w-3" /> Rivalry watch
            <Badge
              variant={data.ai_generated ? "default" : "secondary"}
              className="text-[10px]"
            >
              {data.ai_generated ? "AI-written" : "Auto-generated"}
            </Badge>
          </p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {data.trash_talk}
          </p>
        </div>
      )}
      {data.rivalries.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No rivalries have formed yet.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {data.rivalries.map((r, i) => (
            <div
              key={i}
              className="flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-card/60 p-3"
            >
              <div>
                <p className="font-black flex items-center gap-2">
                  {r.teams[0]} vs {r.teams[1]}
                  {r.grudge_match && (
                    <Badge variant="destructive" className="text-[10px]">
                      Grudge · Wk {r.grudge_week}
                    </Badge>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">
                  {r.series} · {r.meetings} meetings · closest{" "}
                  {r.closest_margin}
                </p>
              </div>
              <Badge variant="secondary" className="font-mono">
                {r.rivalry_index}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --- #100 Committee --------------------------------------------------------

function CommitteeTab({ leagueId }: { leagueId: string }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["coach-committee", leagueId],
    queryFn: () => RecommendationsService.getCommittee(leagueId),
    enabled: !!leagueId,
    retry: false,
  })

  const [ballot, setBallot] = useState<CommitteeRow[] | null>(null)

  // Seed the editable ballot from the blended rankings once loaded.
  useEffect(() => {
    if (data && ballot === null) {
      setBallot([...data.rankings])
    }
  }, [data, ballot])

  const vote = useMutation({
    mutationFn: (rows: CommitteeRow[]) =>
      RecommendationsService.submitCommitteeVote(
        leagueId,
        data?.week,
        rows.map((r, i) => ({ roster_id: r.roster_id, rank: i + 1 })),
      ),
    onSuccess: (res) => {
      toast.success("Ballot submitted")
      queryClient.setQueryData(["coach-committee", leagueId], res)
      setBallot([...res.rankings])
    },
    onError: () => toast.error("Could not submit ballot"),
  })

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null

  const move = (index: number, dir: -1 | 1) => {
    if (!ballot) return
    const next = [...ballot]
    const target = index + dir
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    setBallot(next)
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-lg font-black">Blended Power Rankings</h3>
        <Badge variant="secondary">
          {data.voter_count} {data.voter_count === 1 ? "voter" : "voters"}
        </Badge>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="py-2 pr-2">#</th>
              <th className="py-2 pr-2">Team</th>
              <th className="py-2 pr-2 text-right">Model</th>
              <th className="py-2 pr-2 text-right">Crowd</th>
              <th className="py-2 pr-2 text-right">Disagree</th>
            </tr>
          </thead>
          <tbody>
            {data.rankings.map((r) => (
              <tr key={r.roster_id} className="border-t border-border/50">
                <td className="py-2 pr-2 font-mono font-bold">
                  {r.blended_rank}
                </td>
                <td className="py-2 pr-2">
                  <span className="font-semibold">{r.team}</span>{" "}
                  <span className="text-xs text-muted-foreground">
                    {r.record}
                  </span>
                </td>
                <td className="py-2 pr-2 text-right font-mono">
                  {r.model_rank}
                </td>
                <td className="py-2 pr-2 text-right font-mono">
                  {r.crowd_rank ?? "—"}
                </td>
                <td className="py-2 pr-2 text-right">
                  {r.crowd_rank == null ? (
                    "—"
                  ) : r.disagreement === 0 ? (
                    <span className="text-muted-foreground">0</span>
                  ) : (
                    <span
                      className={
                        r.disagreement > 0
                          ? "text-emerald-500"
                          : "text-rose-500"
                      }
                    >
                      {r.disagreement > 0 ? "+" : ""}
                      {r.disagreement}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {user && ballot && (
        <div className="rounded-lg border border-border/70 bg-card/60 p-4">
          <p className="mb-3 flex items-center gap-2 text-sm font-bold">
            <Vote className="h-4 w-4" /> Your ballot
          </p>
          <div className="flex flex-col gap-1.5">
            {ballot.map((r, i) => (
              <div
                key={r.roster_id}
                className="flex items-center justify-between gap-2 rounded-md bg-secondary/40 px-3 py-1.5 text-sm"
              >
                <span>
                  <span className="mr-2 font-mono font-bold">{i + 1}</span>
                  {r.team}
                </span>
                <span className="flex gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7"
                    disabled={i === 0}
                    onClick={() => move(i, -1)}
                    aria-label={`Move ${r.team} up`}
                  >
                    <ArrowUp className="h-4 w-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7"
                    disabled={i === ballot.length - 1}
                    onClick={() => move(i, 1)}
                    aria-label={`Move ${r.team} down`}
                  >
                    <ArrowDown className="h-4 w-4" />
                  </Button>
                </span>
              </div>
            ))}
          </div>
          <Button
            className="mt-3"
            size="sm"
            disabled={vote.isPending}
            onClick={() => ballot && vote.mutate(ballot)}
          >
            {vote.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Submit ballot"
            )}
          </Button>
        </div>
      )}
      <NoteLine text={data.note} />
    </div>
  )
}

// --- Page ------------------------------------------------------------------

function Coach() {
  const [leagueId, setLeagueId] = useState(
    () => localStorage.getItem("sleeper_league_id") ?? "",
  )
  const [inputLeagueId, setInputLeagueId] = useState(leagueId)
  const [rosterId, setRosterId] = useState<number | null>(null)

  const { data: teams } = useQuery({
    queryKey: ["coach-teams", leagueId],
    queryFn: () => RecommendationsService.getTeams(leagueId),
    enabled: !!leagueId,
    retry: false,
  })

  // Default the per-team picker to the first team once teams load.
  useEffect(() => {
    if (teams && teams.length > 0 && rosterId == null) {
      setRosterId(teams[0].roster_id)
    }
  }, [teams, rosterId])

  const handleSaveLeague = () => {
    const trimmed = inputLeagueId.trim()
    setLeagueId(trimmed)
    setRosterId(null)
    localStorage.setItem("sleeper_league_id", trimmed)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4 flex-wrap rounded-2xl border border-border/70 bg-card/75 p-6 shadow-[0_24px_80px_-52px_rgb(0_0_0/0.9)]">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
            Recommendations
          </p>
          <h1 className="text-3xl font-black tracking-tight flex items-center gap-2">
            <Target className="h-7 w-7 text-primary" />
            Coach
          </h1>
          <p className="text-muted-foreground">
            Start/sit, waivers, trades, playoff outlook, and community rankings
            from your league data
          </p>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-bold uppercase tracking-[0.14em] text-muted-foreground">
            League Configuration
          </CardTitle>
          <CardDescription className="text-xs">
            Enter your Sleeper League ID to generate recommendations.
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
        </CardContent>
      </Card>

      {!leagueId ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 gap-2 text-center">
            <Info className="h-8 w-8 text-muted-foreground" />
            <p className="font-medium">Enter a league ID to get started</p>
            <p className="text-sm text-muted-foreground">
              Coaching tools unlock once a Sleeper league is loaded.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <Tabs defaultValue="start-sit">
              <TabsList className="flex flex-wrap h-auto">
                <TabsTrigger value="start-sit">
                  <ClipboardList className="mr-1 h-4 w-4" /> Start/Sit
                </TabsTrigger>
                <TabsTrigger value="waivers">
                  <TrendingUp className="mr-1 h-4 w-4" /> Waivers
                </TabsTrigger>
                <TabsTrigger value="trades">
                  <Repeat className="mr-1 h-4 w-4" /> Trades
                </TabsTrigger>
                <TabsTrigger value="nudges">
                  <AlertTriangle className="mr-1 h-4 w-4" /> Nudges
                </TabsTrigger>
                <TabsTrigger value="ros">
                  <LineChart className="mr-1 h-4 w-4" /> Outlook
                </TabsTrigger>
                <TabsTrigger value="mustwin">
                  <Target className="mr-1 h-4 w-4" /> Must-Win
                </TabsTrigger>
                <TabsTrigger value="regression">
                  <Scale className="mr-1 h-4 w-4" /> Regression
                </TabsTrigger>
                <TabsTrigger value="rivalries">
                  <Swords className="mr-1 h-4 w-4" /> Rivalries
                </TabsTrigger>
                <TabsTrigger value="committee">
                  <Vote className="mr-1 h-4 w-4" /> Committee
                </TabsTrigger>
              </TabsList>

              {/* Team picker for per-team tabs */}
              {teams && teams.length > 0 && (
                <div className="mt-4 flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                    Team
                  </span>
                  <TeamPicker
                    teams={teams}
                    value={rosterId}
                    onChange={setRosterId}
                  />
                </div>
              )}

              <div className="mt-6">
                <TabsContent value="start-sit">
                  <StartSitTab leagueId={leagueId} rosterId={rosterId} />
                </TabsContent>
                <TabsContent value="waivers">
                  <WaiversTab leagueId={leagueId} rosterId={rosterId} />
                </TabsContent>
                <TabsContent value="trades">
                  <TradesTab leagueId={leagueId} rosterId={rosterId} />
                </TabsContent>
                <TabsContent value="nudges">
                  <NudgesTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="ros">
                  <RosTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="mustwin">
                  <MustWinTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="regression">
                  <RegressionTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="rivalries">
                  <RivalriesTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="committee">
                  <CommitteeTab leagueId={leagueId} />
                </TabsContent>
              </div>
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
