import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react"

/** Table / list spacing density preference. */
export type Density = "comfortable" | "compact"

const DENSITY_KEY = "los_density"

interface PreferencesContextValue {
  density: Density
  setDensity: (density: Density) => void
  toggleDensity: () => void
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null)

function loadDensity(): Density {
  const raw = localStorage.getItem(DENSITY_KEY)
  return raw === "compact" ? "compact" : "comfortable"
}

export function PreferencesProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [density, setDensityState] = useState<Density>(() => loadDensity())

  // Mirror the preference onto <html> so plain CSS (e.g. data tables) can
  // react without threading props through every component.
  useEffect(() => {
    localStorage.setItem(DENSITY_KEY, density)
    document.documentElement.setAttribute("data-density", density)
  }, [density])

  const setDensity = useCallback((next: Density) => {
    setDensityState(next)
  }, [])

  const toggleDensity = useCallback(() => {
    setDensityState((prev) => (prev === "compact" ? "comfortable" : "compact"))
  }, [])

  const value = useMemo<PreferencesContextValue>(
    () => ({ density, setDensity, toggleDensity }),
    [density, setDensity, toggleDensity],
  )

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  )
}

export function usePreferences(): PreferencesContextValue {
  const ctx = useContext(PreferencesContext)
  if (!ctx) {
    throw new Error("usePreferences must be used within a PreferencesProvider")
  }
  return ctx
}
