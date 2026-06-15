import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  BookOpen,
  Flame,
  Info,
  Loader2,
  MessageCircleQuestion,
  Newspaper,
  Send,
  Sparkles,
  Swords,
  Trophy,
} from "lucide-react"
import { useState } from "react"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import useAuth from "@/hooks/useAuth"
import {
  type AskResponse,
  InsightsService,
  type Storyline,
} from "@/lib/footballApi"

export const Route = createFileRoute("/_layout/insights")({
  component: Insights,
  head: () => ({
    meta: [{ title: "Insights - Los Football" }],
  }),
})

function NarrativeBlock({ text }: { text: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none leading-relaxed whitespace-pre-wrap">
      {text}
    </div>
  )
}

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
      <span>{message ?? "Failed to load insight"}</span>
    </div>
  )
}

function AiBadge({ enabled }: { enabled: boolean }) {
  return (
    <Badge variant={enabled ? "default" : "secondary"} className="text-[11px]">
      <Sparkles className="mr-1 h-3 w-3" />
      {enabled ? "AI-written" : "Auto-generated"}
    </Badge>
  )
}

function WeeklyRecapTab({ leagueId }: { leagueId: string }) {
  const { user } = useAuth()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["insights-recap", leagueId],
    queryFn: () => InsightsService.getWeeklyRecap(leagueId),
    enabled: !!leagueId,
    retry: false,
  })

  const publish = useMutation({
    mutationFn: (asDraft: boolean) =>
      InsightsService.publishRecap(leagueId, data?.week, !asDraft),
    onSuccess: (res) =>
      toast.success(
        res.published
          ? `Published "${res.title}" to the blog`
          : `Saved "${res.title}" as a draft`,
      ),
    onError: () => toast.error("Could not publish recap"),
  })

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-black">Week {data.week} Recap</h3>
          <AiBadge enabled={data.ai_enabled} />
        </div>
        {user?.is_superuser && (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={publish.isPending}
              onClick={() => publish.mutate(true)}
            >
              Save draft
            </Button>
            <Button
              size="sm"
              disabled={publish.isPending}
              onClick={() => publish.mutate(false)}
            >
              {publish.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Publish to blog"
              )}
            </Button>
          </div>
        )}
      </div>
      <NarrativeBlock text={data.narrative} />
    </div>
  )
}

function MatchupPreviewsTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["insights-previews", leagueId],
    queryFn: () => InsightsService.getMatchupPreviews(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-black">Week {data.week} Previews</h3>
        <AiBadge enabled={data.ai_enabled} />
      </div>
      <NarrativeBlock text={data.narrative} />
    </div>
  )
}

function WeeklyAwardsTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["insights-awards", leagueId],
    queryFn: () => InsightsService.getWeeklyAwards(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-black">Week {data.week} Awards</h3>
        <AiBadge enabled={data.ai_enabled} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {(data.awards ?? []).map((a) => (
          <div
            key={a.award}
            className="flex items-start gap-3 rounded-lg border border-border/70 bg-card/60 p-3"
          >
            <span className="text-2xl leading-none">{a.emoji}</span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                {a.award}
              </p>
              <p className="font-black">{a.team}</p>
              <p className="text-sm text-muted-foreground">{a.detail}</p>
            </div>
          </div>
        ))}
      </div>
      <NarrativeBlock text={data.narrative} />
    </div>
  )
}

function YearbookTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["insights-yearbook", leagueId],
    queryFn: () => InsightsService.getSeasonYearbook(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-black">
          Season Yearbook · Through Week {data.through_week}
        </h3>
        <AiBadge enabled={data.ai_enabled} />
      </div>
      <NarrativeBlock text={data.narrative} />
    </div>
  )
}

function StorylineCard({ s }: { s: Storyline }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border/70 bg-card/60 p-4">
      <span className="text-2xl leading-none">{s.emoji}</span>
      <div>
        <p className="font-black">{s.title}</p>
        <p className="text-sm text-muted-foreground">{s.detail}</p>
      </div>
    </div>
  )
}

function StorylinesTab({ leagueId }: { leagueId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["insights-storylines", leagueId],
    queryFn: () => InsightsService.getStorylines(leagueId),
    enabled: !!leagueId,
    retry: false,
  })
  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState message={(error as Error)?.message} />
  if (!data) return null
  if (data.storylines.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">
        No storylines detected yet — check back after a few weeks of games.
      </p>
    )
  }
  return (
    <div className="grid gap-3">
      {data.storylines.map((s, i) => (
        <StorylineCard key={`${s.type}-${i}`} s={s} />
      ))}
    </div>
  )
}

function AskTab({ leagueId }: { leagueId: string }) {
  const [question, setQuestion] = useState("")
  const [history, setHistory] = useState<AskResponse[]>([])

  const ask = useMutation({
    mutationFn: (q: string) => InsightsService.ask(q, leagueId),
    onSuccess: (res) => {
      setHistory((h) => [...h, res])
      setQuestion("")
    },
    onError: () => toast.error("Could not get an answer"),
  })

  const submit = () => {
    const q = question.trim()
    if (q) ask.mutate(q)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        {history.map((h, i) => (
          <div key={i} className="flex flex-col gap-2">
            <div className="self-end rounded-lg bg-primary/10 px-3 py-2 text-sm font-medium max-w-[85%]">
              {h.question}
            </div>
            <div className="self-start rounded-lg bg-secondary/70 px-3 py-2 text-sm max-w-[85%] whitespace-pre-wrap">
              {h.answer}
            </div>
          </div>
        ))}
        {ask.isPending && <LoadingState />}
      </div>
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Label htmlFor="ask" className="text-xs mb-1 block">
            Ask anything about your league
          </Label>
          <Textarea
            id="ask"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Who has the most points? Who's on the hottest streak?"
            rows={2}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
          />
        </div>
        <Button onClick={submit} disabled={ask.isPending || !question.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function Insights() {
  const [leagueId, setLeagueId] = useState(
    () => localStorage.getItem("sleeper_league_id") ?? "",
  )
  const [inputLeagueId, setInputLeagueId] = useState(leagueId)

  const { data: meta } = useQuery({
    queryKey: ["insights-meta"],
    queryFn: InsightsService.getMeta,
    retry: false,
  })

  const handleSaveLeague = () => {
    const trimmed = inputLeagueId.trim()
    setLeagueId(trimmed)
    localStorage.setItem("sleeper_league_id", trimmed)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4 flex-wrap rounded-2xl border border-border/70 bg-card/75 p-6 shadow-[0_24px_80px_-52px_rgb(0_0_0/0.9)]">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
            Storytelling
          </p>
          <h1 className="text-3xl font-black tracking-tight flex items-center gap-2">
            <Sparkles className="h-7 w-7 text-primary" />
            Insights
          </h1>
          <p className="text-muted-foreground">
            AI recaps, previews, awards, and storylines powered by your league
            data
          </p>
        </div>
        {meta && (
          <Badge variant={meta.ai_enabled ? "default" : "secondary"}>
            <Sparkles className="mr-1 h-3 w-3" />
            {meta.ai_enabled ? "Claude AI enabled" : "Template mode"}
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-bold uppercase tracking-[0.14em] text-muted-foreground">
            League Configuration
          </CardTitle>
          <CardDescription className="text-xs">
            Enter your Sleeper League ID to generate insights.
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
              Insights unlock once a Sleeper league is loaded.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <Tabs defaultValue="recap">
              <TabsList className="flex flex-wrap h-auto">
                <TabsTrigger value="recap">
                  <Newspaper className="mr-1 h-4 w-4" /> Recap
                </TabsTrigger>
                <TabsTrigger value="previews">
                  <Swords className="mr-1 h-4 w-4" /> Previews
                </TabsTrigger>
                <TabsTrigger value="awards">
                  <Trophy className="mr-1 h-4 w-4" /> Awards
                </TabsTrigger>
                <TabsTrigger value="yearbook">
                  <BookOpen className="mr-1 h-4 w-4" /> Yearbook
                </TabsTrigger>
                <TabsTrigger value="storylines">
                  <Flame className="mr-1 h-4 w-4" /> Storylines
                </TabsTrigger>
                <TabsTrigger value="ask">
                  <MessageCircleQuestion className="mr-1 h-4 w-4" /> Ask
                </TabsTrigger>
              </TabsList>
              <div className="mt-6">
                <TabsContent value="recap">
                  <WeeklyRecapTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="previews">
                  <MatchupPreviewsTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="awards">
                  <WeeklyAwardsTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="yearbook">
                  <YearbookTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="storylines">
                  <StorylinesTab leagueId={leagueId} />
                </TabsContent>
                <TabsContent value="ask">
                  <AskTab leagueId={leagueId} />
                </TabsContent>
              </div>
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
