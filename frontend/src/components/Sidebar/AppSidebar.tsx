import {
  BarChart3,
  BookOpen,
  Briefcase,
  Home,
  ShieldCheck,
  Sparkles,
  Swords,
  Target,
  Users,
  UsersRound,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: BarChart3, title: "Fantasy Stats", path: "/fantasy-stats" },
  { icon: UsersRound, title: "Player Analytics", path: "/player-analytics" },
  { icon: Swords, title: "Matchups", path: "/matchups" },
  { icon: Sparkles, title: "Insights", path: "/insights" },
  { icon: Target, title: "Coach", path: "/coach" },
  { icon: BookOpen, title: "Blog", path: "/blog" },
  { icon: Briefcase, title: "Items", path: "/items" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = currentUser?.is_superuser
    ? [
        ...baseItems,
        { icon: Users, title: "Admin", path: "/admin" },
        { icon: ShieldCheck, title: "Super Admin", path: "/super-admin" },
      ]
    : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
