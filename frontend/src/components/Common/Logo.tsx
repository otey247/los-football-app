import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <span
          className={cn(
            "inline-flex items-center gap-2 group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-black tracking-tight text-primary-foreground shadow-[0_0_24px_-12px_var(--primary)]">
            LF
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-sm font-black uppercase tracking-[0.18em] text-foreground">
              LOS
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-muted-foreground">
              Football
            </span>
          </span>
        </span>
        <span
          className={cn(
            "hidden size-8 items-center justify-center rounded-lg bg-primary text-sm font-black tracking-tight text-primary-foreground shadow-[0_0_24px_-12px_var(--primary)] group-data-[collapsible=icon]:flex",
            className,
          )}
        >
          LF
        </span>
      </>
    ) : (
      <span
        className={cn(
          "inline-flex items-center gap-2",
          variant === "icon" && "gap-0",
          className,
        )}
      >
        <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-sm font-black tracking-tight text-primary-foreground shadow-[0_0_28px_-12px_var(--primary)]">
          LF
        </span>
        {variant === "full" && (
          <span className="flex flex-col leading-none">
            <span className="text-base font-black uppercase tracking-[0.18em] text-foreground">
              LOS
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-muted-foreground">
              Football
            </span>
          </span>
        )}
      </span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
