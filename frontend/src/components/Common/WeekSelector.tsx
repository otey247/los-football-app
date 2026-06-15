import { CalendarDays, Radio } from "lucide-react"

import { Button } from "@/components/ui/button"
import { MAX_WEEK, useLeague } from "@/contexts/LeagueContext"
import { cn } from "@/lib/utils"

export function WeekSelector() {
  const {
    effectiveWeek,
    currentWeek,
    selectedWeek,
    setSelectedWeek,
    hasLeague,
  } = useLeague()

  const isLive = effectiveWeek === currentWeek
  // Percentage position of the live-week marker along the track.
  const currentPct = ((currentWeek - 1) / (MAX_WEEK - 1)) * 100

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border/70 bg-card/60 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-4 w-4 text-primary" />
          <span className="text-sm font-bold">Week</span>
          <span className="text-2xl font-black tabular-nums">
            {effectiveWeek}
          </span>
          {isLive && (
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
              <Radio className="h-3 w-3 animate-pulse" />
              Live
            </span>
          )}
        </div>
        <Button
          variant={selectedWeek === null ? "secondary" : "outline"}
          size="sm"
          className="h-7 text-xs"
          onClick={() => setSelectedWeek(null)}
          disabled={!hasLeague}
        >
          Snap to current
        </Button>
      </div>

      <div className="relative pt-1">
        {/* Live-week tick marker */}
        <div
          className="pointer-events-none absolute -top-0.5 z-10 flex -translate-x-1/2 flex-col items-center"
          style={{ left: `${currentPct}%` }}
        >
          <span className="h-2 w-0.5 rounded-full bg-primary" />
        </div>
        <input
          type="range"
          min={1}
          max={MAX_WEEK}
          step={1}
          value={effectiveWeek}
          disabled={!hasLeague}
          onChange={(e) => setSelectedWeek(Number(e.target.value))}
          aria-label="Select week"
          aria-valuetext={`Week ${effectiveWeek}`}
          className={cn(
            "h-1.5 w-full cursor-pointer appearance-none rounded-full bg-secondary accent-primary",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        />
        <div className="mt-1.5 flex justify-between text-[10px] font-medium tabular-nums text-muted-foreground">
          <span>1</span>
          <span>{Math.ceil(MAX_WEEK / 2)}</span>
          <span>{MAX_WEEK}</span>
        </div>
      </div>
    </div>
  )
}
