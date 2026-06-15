import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  Activity,
  Database,
  GitCompareArrows,
  Info,
  Layers,
  Loader2,
  Mail,
  ScrollText,
  Send,
  Settings2,
  Trash2,
  TrendingUp,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import {
  ReportingService,
  type ScheduledReportCreate,
  SleeperService,
} from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/reporting")({
  component: Reporting,
  head: () => ({
    meta: [{ title: "Reporting - Los Football" }],
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
      <span>{message ?? "Failed to load"}</span>
    </div>
  )
}

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—"
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

// --- #82 / #83 Cache + health ------------------------------------------------
function HealthTab() {
  const cache = useQuery({
    queryKey: ["reporting-cache"],
    queryFn: ReportingService.getCacheStats,
    refetchInterval: 15000,
    retry: false,
  })
  const health = useQuery({
    queryKey: ["reporting-health"],
    queryFn: ReportingService.getHealth,
    refetchInterval: 15000,
    retry: false,
  })

  if (cache.isLoading || health.isLoading) return <LoadingState />
  if (cache.isError)
    return <ErrorState message={(cache.error as Error)?.message} />

  const c = cache.data
  const h = health.data
  const statusColor =
    h?.status === "ok"
      ? "default"
      : h?.status === "warning"
        ? "secondary"
        : "destructive"

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Cache hit rate" value={`${fmt(c?.hit_rate_pct)}%`} />
        <Stat label="Cached entries" value={fmt(c?.cache_entries)} />
        <Stat label="Calls / last min" value={fmt(c?.calls_last_minute)} />
        <Stat
          label="Rate-limit used"
          value={`${fmt(c?.rate_limit_used_pct)}%`}
        />
      </div>

      <Card>
        <CardHeader className="pb-2 flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
              Data Health
            </CardTitle>
            <CardDescription className="text-xs">
              {h?.season
                ? `Season ${h.season} · Week ${h.week}`
                : "Sync status"}
            </CardDescription>
          </div>
          {h && (
            <Badge variant={statusColor} className="uppercase">
              {h.status}
            </Badge>
          )}
        </CardHeader>
        <CardContent>
          {h && h.alerts.length === 0 && (
            <p className="text-sm text-muted-foreground">
              All Sleeper syncs are fresh — no stale or failed data detected.
            </p>
          )}
          {h?.alerts.map((a, i) => (
            <div
              key={i}
              className="mb-1 flex items-center gap-2 rounded-md bg-secondary/60 p-2 text-sm"
            >
              <Badge
                variant={a.level === "error" ? "destructive" : "secondary"}
                className="text-[10px] uppercase"
              >
                {a.level}
              </Badge>
              <span className="font-semibold">{a.endpoint}</span>
              <span className="text-muted-foreground">{a.message}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      {h && h.endpoints.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
              Endpoint Activity
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Endpoint</TableHead>
                  <TableHead className="text-right">OK</TableHead>
                  <TableHead className="text-right">Errors</TableHead>
                  <TableHead className="text-right">Last OK (s)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {h.endpoints.map((e) => (
                  <TableRow key={e.endpoint}>
                    <TableCell className="font-medium">{e.endpoint}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {e.success_count}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {e.error_count}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmt(e.last_success_age_seconds)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card/60 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-2xl font-black tabular-nums">{value}</p>
    </div>
  )
}

// --- #76 Season archive ------------------------------------------------------
function ArchiveTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["reporting-archive", leagueId],
    queryFn: () => ReportingService.getSeasonArchive(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (!leagueId) return <ErrorState message="Set a league ID first." />
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
            All-Time Records ({data.season_count} season
            {data.season_count !== 1 ? "s" : ""})
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Manager</TableHead>
                <TableHead className="text-right">🏆</TableHead>
                <TableHead className="text-right">W</TableHead>
                <TableHead className="text-right">L</TableHead>
                <TableHead className="text-right">Points</TableHead>
                <TableHead className="text-right">Seasons</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.all_time_records.map((r) => (
                <TableRow key={r.user_id}>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.championships}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.wins}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.losses}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {fmt(r.points_for)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.seasons}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {data.seasons.map((s) => (
        <Card key={s.league_id}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-black">
              {s.season} · {s.name}
            </CardTitle>
            <CardDescription className="text-xs">
              {s.champion ? `Champion: ${s.champion}` : "In progress"}
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Team</TableHead>
                  <TableHead className="text-right">W</TableHead>
                  <TableHead className="text-right">L</TableHead>
                  <TableHead className="text-right">PF</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {s.standings.map((st) => (
                  <TableRow key={st.roster_id}>
                    <TableCell className="font-medium">
                      {st.champion ? "🏆 " : ""}
                      {st.name}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {st.wins}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {st.losses}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmt(st.points_for)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// --- #80 Scoring settings ----------------------------------------------------
function ScoringTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["reporting-scoring", leagueId],
    queryFn: () => ReportingService.getScoringSettings(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (!leagueId) return <ErrorState message="Set a league ID first." />
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <Stat label="Scoring format" value={data.scoring_format} />
        <Stat label="Starter slots" value={fmt(data.starter_slots)} />
        <Stat label="Roster size" value={fmt(data.roster_positions.length)} />
      </div>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
            Roster Composition
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {Object.entries(data.roster_composition).map(([pos, count]) => (
            <Badge key={pos} variant="secondary" className="text-xs">
              {count}× {pos}
            </Badge>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
            Key Scoring Rules
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rule</TableHead>
                <TableHead className="text-right">Points</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.scoring_highlights.map((s) => (
                <TableRow key={s.key}>
                  <TableCell className="font-medium">{s.label}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {s.value}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// --- #81 Multi-league --------------------------------------------------------
function MultiLeagueTab() {
  const [input, setInput] = useState("")
  const [username, setUsername] = useState("")
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["reporting-multi", username],
    queryFn: () => ReportingService.getMultiLeague(username),
    enabled: !!username,
    retry: false,
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Label className="mb-1 block text-xs">Sleeper username</Label>
          <Input
            placeholder="e.g. commissioner_joe"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setUsername(input.trim())}
            className="h-8 text-sm"
          />
        </div>
        <Button
          size="sm"
          className="h-8"
          onClick={() => setUsername(input.trim())}
        >
          Load
        </Button>
      </div>
      {isLoading && <LoadingState />}
      {isError && <ErrorState message={(error as Error)?.message} />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Leagues" value={fmt(data.totals.league_count)} />
            <Stat label="Total wins" value={fmt(data.totals.wins)} />
            <Stat label="Total losses" value={fmt(data.totals.losses)} />
            <Stat label="Avg rank" value={fmt(data.totals.avg_rank)} />
          </div>
          <Card>
            <CardContent className="overflow-x-auto pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>League</TableHead>
                    <TableHead className="text-right">Rank</TableHead>
                    <TableHead className="text-right">Record</TableHead>
                    <TableHead className="text-right">PF</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.leagues.map((l) => (
                    <TableRow key={l.league_id}>
                      <TableCell className="font-medium">{l.name}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {l.rank}/{l.total_rosters}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {l.wins}-{l.losses}
                        {l.ties ? `-${l.ties}` : ""}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {fmt(l.points_for)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

// --- #84 Benchmark -----------------------------------------------------------
function BenchmarkTab({ leagueId }: { leagueId: string }) {
  const [rosterId, setRosterId] = useState<string>("")
  const info = useQuery({
    queryKey: ["sleeper-league-info", leagueId],
    queryFn: () => SleeperService.getLeagueInfo(leagueId),
    enabled: !!leagueId,
    retry: false,
  })

  const teams = (() => {
    if (!info.data) return [] as { roster_id: number; name: string }[]
    const userById = new Map(
      info.data.users.map((u) => [
        String(u.user_id),
        u as Record<string, unknown>,
      ]),
    )
    return info.data.rosters.map((r) => {
      const owner = userById.get(String(r.owner_id))
      return {
        roster_id: Number(r.roster_id),
        name: (owner?.display_name as string) ?? `Team ${r.roster_id}`,
      }
    })
  })()

  const bench = useQuery({
    queryKey: ["reporting-benchmark", leagueId, rosterId],
    queryFn: () => ReportingService.getBenchmark(Number(rosterId), leagueId),
    enabled: !!leagueId && !!rosterId,
    retry: false,
  })

  if (!leagueId) return <ErrorState message="Set a league ID first." />

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Label className="mb-1 block text-xs">Team</Label>
          <Select value={rosterId} onValueChange={setRosterId}>
            <SelectTrigger className="h-8 w-64 text-sm">
              <SelectValue placeholder="Choose a team" />
            </SelectTrigger>
            <SelectContent>
              {teams.map((t) => (
                <SelectItem
                  key={t.roster_id}
                  value={String(t.roster_id)}
                  className="text-sm"
                >
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {bench.isLoading && <LoadingState />}
      {bench.isError && (
        <ErrorState message={(bench.error as Error)?.message} />
      )}
      {bench.data && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-black">
              {bench.data.name}
            </CardTitle>
            <CardDescription className="text-xs">
              Through week {bench.data.through_week}
              {bench.data.historical_avg_points !== null &&
                ` · historical avg ${fmt(bench.data.historical_avg_points)} pts/wk`}
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Metric</TableHead>
                  <TableHead className="text-right">Team</TableHead>
                  <TableHead className="text-right">League avg</TableHead>
                  <TableHead className="text-right">Δ</TableHead>
                  <TableHead className="text-right">Pct</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bench.data.metrics.map((m) => {
                  const good = m.higher_is_better ? m.delta >= 0 : m.delta <= 0
                  return (
                    <TableRow key={m.key}>
                      <TableCell className="font-medium">{m.label}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {fmt(m.team_value)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {fmt(m.league_avg)}
                      </TableCell>
                      <TableCell
                        className={`text-right tabular-nums font-semibold ${
                          good ? "text-emerald-500" : "text-destructive"
                        }`}
                      >
                        {m.delta >= 0 ? "+" : ""}
                        {fmt(m.delta)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {m.percentile}%
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// --- #85 Correlations --------------------------------------------------------
function CorrelationsTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["reporting-correlations", leagueId],
    queryFn: () => ReportingService.getCorrelations(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (!leagueId) return <ErrorState message="Set a league ID first." />
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
          Metric Correlations ({data.team_count} teams)
        </CardTitle>
        <CardDescription className="text-xs">
          Pearson correlation across teams. +1 moves together, -1 moves
          opposite.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Relationship</TableHead>
              <TableHead className="text-right">r</TableHead>
              <TableHead className="text-right">Strength</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.pairs.map((p, i) => (
              <TableRow key={i}>
                <TableCell className="font-medium">
                  {p.x_label} → {p.y_label}
                </TableCell>
                <TableCell
                  className={`text-right tabular-nums font-semibold ${
                    p.correlation === null
                      ? ""
                      : p.correlation > 0
                        ? "text-emerald-500"
                        : "text-destructive"
                  }`}
                >
                  {p.correlation === null ? "—" : p.correlation.toFixed(3)}
                </TableCell>
                <TableCell className="text-right">
                  {p.strength ? (
                    <Badge
                      variant="secondary"
                      className="text-[10px] uppercase"
                    >
                      {p.strength} {p.direction}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

// --- #78 Scheduled reports (superuser) --------------------------------------
function ReportsTab({ leagueId }: { leagueId: string }) {
  const qc = useQueryClient()
  const reports = useQuery({
    queryKey: ["reporting-reports"],
    queryFn: ReportingService.listReports,
    retry: false,
  })
  const meta = useQuery({
    queryKey: ["sleeper-meta"],
    queryFn: SleeperService.getStatsMeta,
    retry: false,
  })

  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [statKeys, setStatKeys] = useState<string[]>([])

  const create = useMutation({
    mutationFn: (body: ScheduledReportCreate) =>
      ReportingService.createReport(body),
    onSuccess: () => {
      toast.success("Report saved")
      setName("")
      setEmail("")
      setStatKeys([])
      qc.invalidateQueries({ queryKey: ["reporting-reports"] })
    },
    onError: () => toast.error("Could not save report"),
  })

  const remove = useMutation({
    mutationFn: (id: string) => ReportingService.deleteReport(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reporting-reports"] }),
  })

  const send = useMutation({
    mutationFn: (id: string) => ReportingService.sendReport(id),
    onSuccess: (res) =>
      res.sent
        ? toast.success(`Sent to ${res.recipient}`)
        : toast.warning(res.reason ?? "Email not configured"),
    onError: () => toast.error("Could not send report"),
  })

  const toggleKey = (key: string) =>
    setStatKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    )

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
            New Scheduled Report
          </CardTitle>
          <CardDescription className="text-xs">
            Pick stat cards to bundle and email to the commissioner.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Input
              placeholder="Report name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-8 text-sm"
            />
            <Input
              type="email"
              placeholder="Recipient email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {meta.data?.map((m) => (
              <button
                type="button"
                key={m.key}
                onClick={() => toggleKey(m.key)}
                className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                  statKeys.includes(m.key)
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:bg-accent"
                }`}
              >
                {m.title}
              </button>
            ))}
          </div>
          <div>
            <Button
              size="sm"
              disabled={
                create.isPending ||
                !name.trim() ||
                !email.trim() ||
                statKeys.length === 0
              }
              onClick={() =>
                create.mutate({
                  name: name.trim(),
                  recipient_email: email.trim(),
                  league_id: leagueId,
                  stat_keys: statKeys.join(","),
                  frequency: "weekly",
                  enabled: true,
                })
              }
            >
              Save report
            </Button>
          </div>
        </CardContent>
      </Card>

      {reports.isLoading && <LoadingState />}
      {reports.data?.data.map((r) => (
        <Card key={r.id}>
          <CardContent className="flex items-center justify-between gap-3 py-4">
            <div className="min-w-0">
              <p className="font-semibold">{r.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {r.recipient_email} · {r.stat_keys.split(",").length} cards ·{" "}
                {r.frequency}
                {r.last_sent_at
                  ? ` · last sent ${new Date(r.last_sent_at).toLocaleDateString()}`
                  : " · never sent"}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-8"
                disabled={send.isPending}
                onClick={() => send.mutate(r.id)}
              >
                <Send className="mr-1 h-3 w-3" /> Send now
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-8"
                onClick={() => remove.mutate(r.id)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
      {reports.data && reports.data.count === 0 && (
        <p className="text-sm text-muted-foreground">No saved reports yet.</p>
      )}
    </div>
  )
}

// --- #79 Usage analytics (superuser) ----------------------------------------
function UsageTab() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["reporting-usage"],
    queryFn: ReportingService.getUsageSummary,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
          Product Usage ({data.total_events} events)
        </CardTitle>
        <CardDescription className="text-xs">
          Which cards and views managers engage with most.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Event</TableHead>
              <TableHead>Target</TableHead>
              <TableHead className="text-right">Count</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r, i) => (
              <TableRow key={i}>
                <TableCell>
                  <Badge variant="secondary" className="text-[10px] uppercase">
                    {r.event_type}
                  </Badge>
                </TableCell>
                <TableCell className="font-medium">{r.target}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {r.count}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function Reporting() {
  const { user } = useAuth()
  const [leagueId] = useState(
    () => localStorage.getItem("sleeper_league_id") ?? "",
  )

  useEffect(() => {
    ReportingService.recordUsage("page_view", "reporting", "/reporting")
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-border/70 bg-card/75 p-6 shadow-[0_24px_80px_-52px_rgb(0_0_0/0.9)]">
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
          Data &amp; Instrumentation
        </p>
        <h1 className="flex items-center gap-2 text-3xl font-black tracking-tight">
          <Database className="h-7 w-7 text-primary" />
          Reporting
        </h1>
        <p className="text-muted-foreground">
          Exports, archives, benchmarking, health monitoring and scheduled
          reports for the league.
        </p>
        {leagueId ? (
          <p className="mt-2 text-xs text-muted-foreground">
            League:{" "}
            <code className="font-mono text-foreground">{leagueId}</code>
          </p>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">
            Set a league ID on the Fantasy Stats page to populate these views.
          </p>
        )}
      </div>

      <Tabs defaultValue="health">
        <TabsList className="flex h-auto flex-wrap justify-start">
          <TabsTrigger value="health">
            <Activity className="mr-1 h-4 w-4" /> Health
          </TabsTrigger>
          <TabsTrigger value="archive">
            <ScrollText className="mr-1 h-4 w-4" /> Archive
          </TabsTrigger>
          <TabsTrigger value="scoring">
            <Settings2 className="mr-1 h-4 w-4" /> Scoring
          </TabsTrigger>
          <TabsTrigger value="multi">
            <Layers className="mr-1 h-4 w-4" /> Multi-League
          </TabsTrigger>
          <TabsTrigger value="benchmark">
            <TrendingUp className="mr-1 h-4 w-4" /> Benchmark
          </TabsTrigger>
          <TabsTrigger value="correlations">
            <GitCompareArrows className="mr-1 h-4 w-4" /> Correlations
          </TabsTrigger>
          {user?.is_superuser && (
            <TabsTrigger value="reports">
              <Mail className="mr-1 h-4 w-4" /> Reports
            </TabsTrigger>
          )}
          {user?.is_superuser && (
            <TabsTrigger value="usage">
              <Activity className="mr-1 h-4 w-4" /> Usage
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="health" className="mt-4">
          <HealthTab />
        </TabsContent>
        <TabsContent value="archive" className="mt-4">
          <ArchiveTab leagueId={leagueId} />
        </TabsContent>
        <TabsContent value="scoring" className="mt-4">
          <ScoringTab leagueId={leagueId} />
        </TabsContent>
        <TabsContent value="multi" className="mt-4">
          <MultiLeagueTab />
        </TabsContent>
        <TabsContent value="benchmark" className="mt-4">
          <BenchmarkTab leagueId={leagueId} />
        </TabsContent>
        <TabsContent value="correlations" className="mt-4">
          <CorrelationsTab leagueId={leagueId} />
        </TabsContent>
        {user?.is_superuser && (
          <TabsContent value="reports" className="mt-4">
            <ReportsTab leagueId={leagueId} />
          </TabsContent>
        )}
        {user?.is_superuser && (
          <TabsContent value="usage" className="mt-4">
            <UsageTab />
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
