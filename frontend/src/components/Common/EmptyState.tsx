import { cn } from "@/lib/utils"

type Illustration = "field" | "preseason" | "search" | "error"

interface EmptyStateProps {
  illustration?: Illustration
  title: string
  description?: string
  /** Optional action node (e.g. a retry / configure button). */
  action?: React.ReactNode
  className?: string
}

/**
 * A friendly, theme-aware empty state with an inline SVG illustration.
 *
 * Use for pre-season / no-data scenarios, empty search results, and per-card
 * error fallbacks so blank screens feel intentional rather than broken.
 */
export function EmptyState({
  illustration = "field",
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 px-6 py-10 text-center",
        className,
      )}
    >
      <Illustration variant={illustration} />
      <div className="space-y-1">
        <p className="text-base font-bold">{title}</p>
        {description && (
          <p className="mx-auto max-w-sm text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  )
}

function Illustration({ variant }: { variant: Illustration }) {
  return (
    <svg
      role="presentation"
      aria-hidden="true"
      width="132"
      height="100"
      viewBox="0 0 132 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="text-primary"
    >
      <title>{variant}</title>
      {/* Soft pedestal shadow shared by every illustration. */}
      <ellipse
        cx="66"
        cy="90"
        rx="46"
        ry="7"
        fill="currentColor"
        opacity="0.08"
      />
      {variant === "field" && <FieldArt />}
      {variant === "preseason" && <PreseasonArt />}
      {variant === "search" && <SearchArt />}
      {variant === "error" && <ErrorArt />}
    </svg>
  )
}

/** A football resting on a yard-lined field — the default "no data" mark. */
function FieldArt() {
  return (
    <>
      <rect
        x="20"
        y="40"
        width="92"
        height="44"
        rx="8"
        fill="currentColor"
        opacity="0.1"
      />
      <line
        x1="44"
        y1="40"
        x2="44"
        y2="84"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeWidth="2"
        strokeDasharray="4 5"
      />
      <line
        x1="66"
        y1="40"
        x2="66"
        y2="84"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeWidth="2"
        strokeDasharray="4 5"
      />
      <line
        x1="88"
        y1="40"
        x2="88"
        y2="84"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeWidth="2"
        strokeDasharray="4 5"
      />
      <ellipse cx="66" cy="44" rx="20" ry="13" fill="currentColor" />
      <path
        d="M56 44h20M62 39v10M70 39v10"
        stroke="var(--primary-foreground)"
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.9"
      />
    </>
  )
}

/** A whistle / calendar feel for "season hasn't started yet". */
function PreseasonArt() {
  return (
    <>
      <rect
        x="34"
        y="30"
        width="64"
        height="54"
        rx="9"
        fill="currentColor"
        opacity="0.12"
      />
      <rect
        x="34"
        y="30"
        width="64"
        height="16"
        rx="9"
        fill="currentColor"
        opacity="0.3"
      />
      <circle cx="48" cy="24" r="4" fill="currentColor" />
      <circle cx="84" cy="24" r="4" fill="currentColor" />
      <rect x="46" y="20" width="4" height="12" rx="2" fill="currentColor" />
      <rect x="82" y="20" width="4" height="12" rx="2" fill="currentColor" />
      <path
        d="M52 62l8 8 18-18"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </>
  )
}

/** A magnifier for empty search / filter results. */
function SearchArt() {
  return (
    <>
      <circle
        cx="58"
        cy="50"
        r="22"
        fill="currentColor"
        opacity="0.12"
        stroke="currentColor"
        strokeOpacity="0.4"
        strokeWidth="3"
      />
      <line
        x1="74"
        y1="66"
        x2="92"
        y2="84"
        stroke="currentColor"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <line
        x1="50"
        y1="50"
        x2="66"
        y2="50"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        opacity="0.5"
      />
    </>
  )
}

/** A broken-link / alert glyph for error fallbacks. */
function ErrorArt() {
  return (
    <>
      <path
        d="M66 26l40 58H26L66 26z"
        fill="currentColor"
        opacity="0.12"
        stroke="currentColor"
        strokeOpacity="0.4"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <line
        x1="66"
        y1="48"
        x2="66"
        y2="66"
        stroke="currentColor"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <circle cx="66" cy="76" r="3.5" fill="currentColor" />
    </>
  )
}
