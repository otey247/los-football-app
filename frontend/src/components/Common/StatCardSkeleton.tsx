import { Skeleton } from "@/components/ui/skeleton"
import { usePreferences } from "@/contexts/PreferencesContext"
import { cn } from "@/lib/utils"

interface StatRowsSkeletonProps {
  /** How many placeholder rows to render. */
  rows?: number
  className?: string
}

/**
 * Placeholder rows shown inside an expanded stat card while its Sleeper data
 * is in flight. Mirrors the layout of a real `StatRow` to avoid layout shift.
 */
export function StatRowsSkeleton({
  rows = 6,
  className,
}: StatRowsSkeletonProps) {
  const { density } = usePreferences()
  return (
    <div className={cn("divide-y divide-border/60", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={`stat-row-skeleton-${i}`}
          className={cn(
            "flex items-center justify-between px-3",
            density === "compact" ? "py-1.5" : "py-2.5",
          )}
        >
          <div className="flex min-w-0 items-center gap-3">
            <Skeleton className="h-4 w-4 rounded" />
            <Skeleton className="h-8 w-8 rounded-full" />
            <Skeleton className="h-4 w-28" />
          </div>
          <div className="flex shrink-0 gap-4">
            <Skeleton className="h-7 w-12" />
            <Skeleton className="h-7 w-12" />
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Full stat-card placeholder for the initial grid load, before the stat
 * catalog has resolved.
 */
export function StatCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-card/95 p-6 shadow-[0_18px_60px_-36px_rgb(0_0_0/0.9)]">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-20 rounded-full" />
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-3 w-52" />
        </div>
        <Skeleton className="h-8 w-8 rounded-md" />
      </div>
    </div>
  )
}
