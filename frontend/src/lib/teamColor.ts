// Team-color theming.
//
// Sleeper does not expose a per-franchise brand color, so we derive a vivid,
// stable color from a team's seed (roster id, display name, or avatar id).
// Colors are emitted in OKLch to match the design tokens in `index.css`, and
// the same seed always maps to the same hue so a team's accent is consistent
// across every stat card, standings row, and matchup view.

export interface TeamColor {
  /** Hue angle (0-359) used to derive the rest of the palette. */
  hue: number
  /** Solid accent color — good for text, icons, and rank badges. */
  color: string
  /** Translucent fill — good for chips, badges, and row backgrounds. */
  soft: string
  /** Translucent border/ring tint. */
  border: string
}

/**
 * Map an arbitrary seed to a deterministic {@link TeamColor}.
 *
 * Uses a small FNV-style string hash so the mapping is stable across reloads
 * and identical between server-rendered and client-rendered output.
 */
export function teamColorFromSeed(
  seed: string | number | null | undefined,
): TeamColor {
  const str = String(seed ?? "")
  let hash = 2166136261
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  const hue = Math.abs(hash) % 360
  return {
    hue,
    color: `oklch(0.62 0.19 ${hue})`,
    soft: `oklch(0.62 0.19 ${hue} / 0.16)`,
    border: `oklch(0.62 0.19 ${hue} / 0.55)`,
  }
}

/** Derive up-to-two-letter initials from a team / manager display name. */
export function teamInitials(name: string | null | undefined): string {
  const parts = String(name ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  if (parts.length === 0) return "?"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}
