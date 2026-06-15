import { useEffect, useRef, useState } from "react"

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion"
import { cn } from "@/lib/utils"

interface AnimatedNumberProps {
  value: number
  /** Decimal places. Defaults to 0 for integers, 2 otherwise. */
  decimals?: number
  prefix?: string
  suffix?: string
  /** Animation length in ms. */
  duration?: number
  /** Count up from zero when the value first appears. Defaults to true. */
  animateOnMount?: boolean
  className?: string
}

/** easeOutCubic — fast start, gentle settle. */
function easeOutCubic(t: number): number {
  return 1 - (1 - t) ** 3
}

/**
 * A number that counts up (or down) to its target value with a smooth tween.
 *
 * Used for points, ranks, and win probabilities. Honors `prefers-reduced-motion`
 * by snapping straight to the target value.
 */
export function AnimatedNumber({
  value,
  decimals,
  prefix = "",
  suffix = "",
  duration = 700,
  animateOnMount = true,
  className,
}: AnimatedNumberProps) {
  const reduced = usePrefersReducedMotion()
  const initial = animateOnMount ? 0 : value
  const [display, setDisplay] = useState(initial)
  const displayRef = useRef(initial)
  const fromRef = useRef(initial)
  const rafRef = useRef<number | null>(null)

  const places = decimals ?? (Number.isInteger(value) ? 0 : 2)

  useEffect(() => {
    if (reduced || fromRef.current === value) {
      setDisplay(value)
      displayRef.current = value
      fromRef.current = value
      return
    }

    const from = fromRef.current
    const to = value
    const start = performance.now()

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const current = from + (to - from) * easeOutCubic(t)
      displayRef.current = current
      setDisplay(current)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = to
      }
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      // Resume from wherever we left off if interrupted mid-tween.
      fromRef.current = displayRef.current
    }
  }, [value, duration, reduced])

  const formatted = display.toLocaleString(undefined, {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
  })

  return (
    <span className={cn("tabular-nums", className)}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  )
}
