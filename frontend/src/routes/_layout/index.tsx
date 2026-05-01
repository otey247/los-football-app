import { createFileRoute } from "@tanstack/react-router"

import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - FastAPI Template",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-border/70 bg-card/80 p-8 shadow-[0_24px_80px_-48px_rgb(0_0_0/0.9)]">
        <p className="mb-3 text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
          Command Center
        </p>
        <h1 className="max-w-3xl truncate text-3xl font-black tracking-tight md:text-4xl">
          Hi, {currentUser?.full_name || currentUser?.email}
        </h1>
        <p className="mt-2 text-muted-foreground">
          Welcome back to your LOS Football analytics workspace.
        </p>
      </div>
    </div>
  )
}
