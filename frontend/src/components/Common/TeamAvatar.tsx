import { useState } from "react"

import { teamColorFromSeed, teamInitials } from "@/lib/teamColor"
import { cn } from "@/lib/utils"

interface TeamAvatarProps {
  /** Sleeper avatar id (not a full URL). */
  avatar?: string | null
  /** Team / manager display name — used for alt text and initials fallback. */
  name?: string | null
  /** Stable seed for the team color; falls back to name, then avatar. */
  seed?: string | number | null
  /** Size + extra classes. Defaults to `h-8 w-8`. */
  className?: string
  /** Render a team-colored ring around the avatar. */
  ring?: boolean
}

/**
 * Avatar used across standings, matchups, and stat cards.
 *
 * Renders the Sleeper-hosted avatar when available and gracefully falls back to
 * team-colored initials when the id is missing or the image fails to load, so
 * every team has a recognisable mark throughout the app.
 */
export function TeamAvatar({
  avatar,
  name,
  seed,
  className,
  ring = true,
}: TeamAvatarProps) {
  const [failed, setFailed] = useState(false)
  const displayName = name ?? "Team"
  const tc = teamColorFromSeed(seed ?? name ?? avatar)
  const ringStyle = ring
    ? { boxShadow: `0 0 0 2px ${tc.border}` }
    : { boxShadow: "0 0 0 1px var(--border)" }

  if (avatar && !failed) {
    return (
      <img
        src={`https://sleepercdn.com/avatars/thumbs/${avatar}`}
        alt={displayName}
        loading="lazy"
        onError={() => setFailed(true)}
        style={ringStyle}
        className={cn(
          "h-8 w-8 shrink-0 rounded-full bg-secondary object-cover",
          className,
        )}
      />
    )
  }

  return (
    <div
      aria-label={displayName}
      role="img"
      style={{ backgroundColor: tc.soft, color: tc.color, ...ringStyle }}
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-black uppercase leading-none",
        className,
      )}
    >
      {teamInitials(displayName)}
    </div>
  )
}
