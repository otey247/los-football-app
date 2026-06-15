import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { useEffect, useState } from "react"

import { Breadcrumbs } from "@/components/Common/Breadcrumbs"
import { CommandPalette } from "@/components/Common/CommandPalette"
import { Footer } from "@/components/Common/Footer"
import { LeagueSwitcher } from "@/components/Common/LeagueSwitcher"
import { MobileTabBar } from "@/components/Common/MobileTabBar"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import { Button } from "@/components/ui/button"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  const [commandOpen, setCommandOpen] = useState(false)

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setCommandOpen((open) => !open)
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 border-b border-border/70 bg-background/78 px-4 backdrop-blur-xl">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
          <div className="hidden min-w-0 flex-1 sm:block">
            <Breadcrumbs />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCommandOpen(true)}
              className="h-8 gap-2 text-muted-foreground"
              aria-label="Open command palette"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Search</span>
              <kbd className="hidden rounded border border-border/70 bg-muted px-1.5 font-mono text-[10px] sm:inline">
                ⌘K
              </kbd>
            </Button>
            <LeagueSwitcher />
          </div>
        </header>
        <main className="flex-1 p-6 pb-24 md:p-8 md:pb-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
        <Footer />
        <MobileTabBar />
      </SidebarInset>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </SidebarProvider>
  )
}

export default Layout
