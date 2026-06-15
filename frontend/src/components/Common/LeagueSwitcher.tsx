import { Check, ChevronsUpDown, Plus, Trophy, X } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { type SavedLeague, useLeague } from "@/contexts/LeagueContext"
import { cn } from "@/lib/utils"

function LeagueAvatar({ league }: { league?: SavedLeague }) {
  if (league?.avatar) {
    return (
      <img
        src={`https://sleepercdn.com/avatars/thumbs/${league.avatar}`}
        alt={league.name}
        className="h-5 w-5 shrink-0 rounded-md ring-1 ring-border/70"
      />
    )
  }
  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-secondary ring-1 ring-border/70">
      <Trophy className="h-3 w-3 text-muted-foreground" />
    </span>
  )
}

export function LeagueSwitcher() {
  const {
    leagues,
    activeLeagueId,
    activeLeague,
    setActiveLeague,
    addLeague,
    removeLeague,
  } = useLeague()
  const [open, setOpen] = useState(false)
  const [newId, setNewId] = useState("")

  const handleAdd = () => {
    const trimmed = newId.trim()
    if (!trimmed) return
    addLeague(trimmed)
    setNewId("")
    setOpen(false)
  }

  const label = activeLeague?.name || activeLeagueId || "Select league"

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 max-w-[12rem] gap-2"
          aria-label="Switch league"
        >
          <LeagueAvatar league={activeLeague} />
          <span className="truncate font-semibold">{label}</span>
          <ChevronsUpDown className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
          Your leagues
        </DropdownMenuLabel>
        {leagues.length === 0 && (
          <p className="px-2 py-1.5 text-xs text-muted-foreground">
            No leagues yet — add one below.
          </p>
        )}
        {leagues.map((league) => (
          <DropdownMenuItem
            key={league.id}
            className="gap-2"
            onSelect={(e) => {
              e.preventDefault()
              setActiveLeague(league.id)
              setOpen(false)
            }}
          >
            <LeagueAvatar league={league} />
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-medium">
                {league.name || league.id}
              </span>
              {league.name && league.name !== league.id && (
                <span className="truncate font-mono text-[10px] text-muted-foreground">
                  {league.id}
                </span>
              )}
            </span>
            <Check
              className={cn(
                "ml-auto h-4 w-4 shrink-0",
                league.id === activeLeagueId ? "opacity-100" : "opacity-0",
              )}
            />
            <button
              type="button"
              aria-label={`Remove ${league.name || league.id}`}
              className="rounded p-0.5 text-muted-foreground hover:text-destructive"
              onClick={(e) => {
                e.stopPropagation()
                removeLeague(league.id)
              }}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <div className="flex items-center gap-2 p-2">
          <Input
            placeholder="Add Sleeper league ID"
            value={newId}
            onChange={(e) => setNewId(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd()
            }}
            className="h-8 text-sm"
          />
          <Button
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={handleAdd}
            disabled={!newId.trim()}
            aria-label="Add league"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
