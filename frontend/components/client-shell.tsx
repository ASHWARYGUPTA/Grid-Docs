"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { useAuth } from "@/context/auth-context";
import { TourProvider } from "@/components/onboarding-tour";

/**
 * ClientShell — handles auth gating, sidebar layout, and onboarding tour.
 *
 * - /, /login  → renders children directly (no sidebar, no auth check)
 * - other      → if unauthenticated, redirects to /login
 *                if authenticated, wraps children in sidebar shell + tour provider
 */
export function ClientShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isPublicRoute = pathname === "/login" || pathname === "/";

  useEffect(() => {
    if (!loading && !user && !isPublicRoute) {
      router.replace("/login");
    }
  }, [loading, user, isPublicRoute, router]);

  // Public routes — no sidebar, no auth check, no tour
  if (isPublicRoute) {
    return <>{children}</>;
  }

  // Hydrating — minimal loader to avoid flash
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="size-8 rounded-xl bg-primary animate-pulse" />
          <p className="text-sm text-muted-foreground">Loading…</p>
        </div>
      </div>
    );
  }

  // Not authenticated — null while redirect fires
  if (!user) return null;

  // Authenticated — full dashboard shell with onboarding tour
  return (
    <TourProvider userEmail={user.email}>
      <SidebarProvider defaultOpen={true}>
        <AppSidebar />
        <SidebarInset className="overflow-hidden">
          {children}
        </SidebarInset>
      </SidebarProvider>
    </TourProvider>
  );
}
