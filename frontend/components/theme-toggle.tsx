"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch — render nothing until mounted
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="size-7" />;

  const isDark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-7 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? (
        <Sun className="size-4 transition-all" />
      ) : (
        <Moon className="size-4 transition-all" />
      )}
    </Button>
  );
}
