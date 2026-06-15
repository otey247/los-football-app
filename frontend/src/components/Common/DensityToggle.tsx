import { Rows2, Rows3 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { usePreferences } from "@/contexts/PreferencesContext"

/**
 * Toggles list/table spacing between "comfortable" and "compact" for
 * data-heavy views. The choice is persisted per user.
 */
export function DensityToggle() {
  const { density, toggleDensity } = usePreferences()
  const isCompact = density === "compact"
  const label = isCompact
    ? "Switch to comfortable density"
    : "Switch to compact density"

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          onClick={toggleDensity}
          className="h-8 gap-2 text-muted-foreground"
          aria-label={label}
          aria-pressed={isCompact}
          data-testid="density-toggle"
        >
          {isCompact ? (
            <Rows3 className="h-3.5 w-3.5" />
          ) : (
            <Rows2 className="h-3.5 w-3.5" />
          )}
          <span className="hidden sm:inline">
            {isCompact ? "Compact" : "Comfortable"}
          </span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
