import { useQuery } from "@tanstack/react-query"
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react"

import { SleeperService } from "@/lib/footballApi"

export interface SavedLeague {
  id: string
  name: string
  avatar?: string | null
}

const LEAGUES_KEY = "los_leagues"
// Reuse the legacy key so existing users keep their configured league.
const ACTIVE_KEY = "sleeper_league_id"
const FAVORITES_KEY = "los_favorite_stats"

export const MAX_WEEK = 18

interface LeagueContextValue {
  leagues: SavedLeague[]
  activeLeagueId: string
  activeLeague: SavedLeague | undefined
  /** User-selected week, or null when following the live week. */
  selectedWeek: number | null
  /** The live NFL week for the active league. */
  currentWeek: number
  /** selectedWeek when set, otherwise the live week. */
  effectiveWeek: number
  favorites: string[]
  hasLeague: boolean
  addLeague: (id: string) => void
  removeLeague: (id: string) => void
  setActiveLeague: (id: string) => void
  setSelectedWeek: (week: number | null) => void
  toggleFavorite: (key: string) => void
  isFavorite: (key: string) => boolean
}

const LeagueContext = createContext<LeagueContextValue | null>(null)

function loadLeagues(): SavedLeague[] {
  try {
    const raw = localStorage.getItem(LEAGUES_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return parsed.filter(
          (l): l is SavedLeague => !!l && typeof l.id === "string",
        )
      }
    }
  } catch {
    // ignore malformed storage
  }
  const legacy = localStorage.getItem(ACTIVE_KEY)
  return legacy ? [{ id: legacy, name: legacy }] : []
}

function loadFavorites(): string[] {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return parsed.filter((k): k is string => typeof k === "string")
      }
    }
  } catch {
    // ignore malformed storage
  }
  return []
}

export function LeagueProvider({ children }: { children: React.ReactNode }) {
  const initialLeagues = loadLeagues()
  const [leagues, setLeagues] = useState<SavedLeague[]>(initialLeagues)
  const [activeLeagueId, setActiveLeagueIdState] = useState<string>(
    () => localStorage.getItem(ACTIVE_KEY) || initialLeagues[0]?.id || "",
  )
  const [selectedWeek, setSelectedWeekState] = useState<number | null>(null)
  const [favorites, setFavorites] = useState<string[]>(() => loadFavorites())

  useEffect(() => {
    localStorage.setItem(LEAGUES_KEY, JSON.stringify(leagues))
  }, [leagues])

  useEffect(() => {
    localStorage.setItem(ACTIVE_KEY, activeLeagueId)
  }, [activeLeagueId])

  useEffect(() => {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites))
  }, [favorites])

  const { data: leagueInfo } = useQuery({
    queryKey: ["league-info", activeLeagueId],
    queryFn: () => SleeperService.getLeagueInfo(activeLeagueId),
    enabled: !!activeLeagueId,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  const currentWeek = useMemo(() => {
    const state = leagueInfo?.nfl_state
    const wk = state ? Number(state.week ?? state.display_week ?? 1) : 1
    if (!Number.isFinite(wk) || wk < 1) return 1
    return Math.min(Math.trunc(wk), MAX_WEEK)
  }, [leagueInfo])

  // Backfill the active league's display name/avatar once Sleeper responds.
  useEffect(() => {
    const lg = leagueInfo?.league
    if (!lg || !activeLeagueId) return
    const name = typeof lg.name === "string" ? lg.name : ""
    const avatar = typeof lg.avatar === "string" ? lg.avatar : null
    if (!name) return
    setLeagues((prev) =>
      prev.map((l) =>
        l.id === activeLeagueId && (l.name !== name || l.avatar !== avatar)
          ? { ...l, name, avatar }
          : l,
      ),
    )
  }, [leagueInfo, activeLeagueId])

  const addLeague = useCallback((rawId: string) => {
    const id = rawId.trim()
    if (!id) return
    setLeagues((prev) =>
      prev.some((l) => l.id === id) ? prev : [...prev, { id, name: id }],
    )
    setActiveLeagueIdState(id)
    setSelectedWeekState(null)
  }, [])

  const removeLeague = useCallback((id: string) => {
    setLeagues((prev) => {
      const next = prev.filter((l) => l.id !== id)
      setActiveLeagueIdState((cur) => (cur === id ? (next[0]?.id ?? "") : cur))
      return next
    })
  }, [])

  const setActiveLeague = useCallback((id: string) => {
    setActiveLeagueIdState(id)
    setSelectedWeekState(null)
  }, [])

  const setSelectedWeek = useCallback((week: number | null) => {
    if (week === null) {
      setSelectedWeekState(null)
      return
    }
    const clamped = Math.min(Math.max(Math.trunc(week), 1), MAX_WEEK)
    setSelectedWeekState(clamped)
  }, [])

  const toggleFavorite = useCallback((key: string) => {
    setFavorites((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    )
  }, [])

  const isFavorite = useCallback(
    (key: string) => favorites.includes(key),
    [favorites],
  )

  const activeLeague = useMemo(
    () => leagues.find((l) => l.id === activeLeagueId),
    [leagues, activeLeagueId],
  )

  const value = useMemo<LeagueContextValue>(
    () => ({
      leagues,
      activeLeagueId,
      activeLeague,
      selectedWeek,
      currentWeek,
      effectiveWeek: selectedWeek ?? currentWeek,
      favorites,
      hasLeague: !!activeLeagueId,
      addLeague,
      removeLeague,
      setActiveLeague,
      setSelectedWeek,
      toggleFavorite,
      isFavorite,
    }),
    [
      leagues,
      activeLeagueId,
      activeLeague,
      selectedWeek,
      currentWeek,
      favorites,
      addLeague,
      removeLeague,
      setActiveLeague,
      setSelectedWeek,
      toggleFavorite,
      isFavorite,
    ],
  )

  return (
    <LeagueContext.Provider value={value}>{children}</LeagueContext.Provider>
  )
}

export function useLeague(): LeagueContextValue {
  const ctx = useContext(LeagueContext)
  if (!ctx) {
    throw new Error("useLeague must be used within a LeagueProvider")
  }
  return ctx
}
