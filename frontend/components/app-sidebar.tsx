"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  BarChart3,
  CalendarClock,
  LayoutGrid,
  LogOut,
  Send,
  ShieldCheck,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/context/auth-context";
import { ROLE_BADGE_STYLES, ROLE_LABELS, type Role } from "@/lib/auth";
import { useTour } from "@/components/onboarding-tour";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/live",       label: "Live Monitor",   icon: Activity },
  { href: "/planned",    label: "Planned Events",  icon: CalendarClock },
  { href: "/governance", label: "Governance",      icon: ShieldCheck },
  { href: "/analytics",  label: "Analytics",       icon: BarChart3 },
  { href: "/report",     label: "Citizen Report",  icon: Send },
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { startTour } = useTour();

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <Sidebar variant="inset" collapsible="icon">
      {/* Header / Brand */}
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip="Grid Unlocked"
              render={
                <Link href="/live" className="flex items-center gap-2">
                  <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm shrink-0">
                    <LayoutGrid className="size-4" />
                  </div>
                  <div className="flex flex-col gap-0.5 leading-none min-w-0">
                    <span className="font-semibold text-sm truncate">Grid Unlocked</span>
                    <span className="text-[11px] text-sidebar-foreground/60 truncate">
                      Command Dashboard
                    </span>
                  </div>
                </Link>
              }
            />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarSeparator />

      {/* Navigation */}
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarMenu className="gap-1.5" id="tour-sidebar-nav">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const isActive = !!pathname?.startsWith(href);
              return (
                <SidebarMenuItem key={href}>
                  <SidebarMenuButton
                    isActive={isActive}
                    tooltip={label}
                    render={
                      <Link href={href} className="flex items-center gap-2">
                        <Icon className="size-4 shrink-0" />
                        <span>{label}</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      {/* Footer */}
      <SidebarFooter>
        <SidebarSeparator />

        {/* User info — visible when sidebar is expanded */}
        {user && (
          <div className="flex items-center gap-2 px-2 py-2 group-data-[collapsible=icon]:hidden">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-medium truncate leading-tight">{user.name}</span>
              <Badge
                variant="outline"
                className={cn(
                  "mt-0.5 w-fit text-[10px] py-0 h-4 leading-none",
                  ROLE_BADGE_STYLES[user.role as Role]
                )}
              >
                {ROLE_LABELS[user.role as Role]}
              </Badge>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
              onClick={handleLogout}
              title="Sign out"
            >
              <LogOut className="size-3.5" />
            </Button>
          </div>
        )}

        {/* Replay tour link — expanded only */}
        <button
          onClick={startTour}
          className="text-[10px] text-muted-foreground/60 hover:text-muted-foreground transition-colors text-center py-1 w-full group-data-[collapsible=icon]:hidden"
        >
          Replay tour
        </button>

        {/* Theme + logout icon — always visible, logout only shown collapsed */}
        <div className="flex items-center justify-center px-2 py-1">
          <ThemeToggle />
          {user && (
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-muted-foreground hover:text-foreground hidden group-data-[collapsible=icon]:flex"
              onClick={handleLogout}
              title="Sign out"
            >
              <LogOut className="size-3.5" />
            </Button>
          )}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
