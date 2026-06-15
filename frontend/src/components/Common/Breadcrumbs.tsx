import { useQuery } from "@tanstack/react-query"
import { Link, useRouterState } from "@tanstack/react-router"
import { Fragment } from "react"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { useLeague } from "@/contexts/LeagueContext"
import { SleeperService } from "@/lib/footballApi"

// Maps the top-level route segment to a human label.
const SECTION_LABELS: Record<string, string> = {
  "": "Dashboard",
  "fantasy-stats": "Fantasy Stats",
  insights: "Insights",
  blog: "Blog",
  items: "Items",
  settings: "Settings",
  admin: "Admin",
  "super-admin": "Super Admin",
}

interface Crumb {
  label: string
  to?: string
}

export function Breadcrumbs() {
  const router = useRouterState()
  const pathname = router.location.pathname
  const search = router.location.search as Record<string, unknown>
  const { activeLeague, activeLeagueId } = useLeague()

  // Stat metadata lets us name the focused stat card in the trail.
  const { data: statsMeta } = useQuery({
    queryKey: ["sleeper-meta"],
    queryFn: SleeperService.getStatsMeta,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  })

  const segments = pathname.split("/").filter(Boolean)
  const section = segments[0] ?? ""

  const crumbs: Crumb[] = []

  // League acts as the root of every drill-down path.
  const leagueLabel = activeLeague?.name || activeLeagueId
  if (leagueLabel) {
    crumbs.push({ label: leagueLabel, to: "/" })
  }

  const sectionLabel = SECTION_LABELS[section]
  if (sectionLabel && section !== "") {
    crumbs.push({ label: sectionLabel, to: `/${section}` })
  } else if (!leagueLabel) {
    crumbs.push({ label: "Dashboard", to: "/" })
  }

  // Deep-link drill-down: a focused stat card on the fantasy stats page.
  if (section === "fantasy-stats" && typeof search.stat === "string") {
    const meta = statsMeta?.find((s) => s.key === search.stat)
    crumbs.push({ label: meta?.title ?? search.stat })
  }

  // Blog post detail.
  if (section === "blog" && segments[1]) {
    crumbs.push({ label: "Post" })
  }

  if (crumbs.length === 0) {
    crumbs.push({ label: "Dashboard" })
  }

  // The final crumb is the current page (no link).
  return (
    <Breadcrumb className="min-w-0">
      <BreadcrumbList>
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1
          return (
            <Fragment key={`${crumb.label}-${i}`}>
              <BreadcrumbItem className="min-w-0">
                {isLast || !crumb.to ? (
                  <BreadcrumbPage className="truncate">
                    {crumb.label}
                  </BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <Link to={crumb.to} className="truncate">
                      {crumb.label}
                    </Link>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
              {!isLast && <BreadcrumbSeparator />}
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
