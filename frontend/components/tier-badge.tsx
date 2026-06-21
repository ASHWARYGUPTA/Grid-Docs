"use client";

import { useEffect, useState } from "react";
import { Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useDashboardSocket } from "@/lib/ws";
import type { GovernanceTierResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const TIER_CONFIG: Record<
  string,
  {
    variant: "default" | "secondary" | "destructive";
    dot: string;
    label: string;
  }
> = {
  "1": {
    variant: "default",
    dot: "bg-live",
    label: "Tier 1",
  },
  "2": {
    variant: "secondary",
    dot: "bg-warn",
    label: "Tier 2",
  },
  "3": {
    variant: "destructive",
    dot: "bg-critical animate-pulse-ring",
    label: "Tier 3",
  },
};

const POLL_INTERVAL_MS = 30_000;

export function TierBadge() {
  const [tier, setTier] = useState<GovernanceTierResponse | null>(null);
  const { lastDelta } = useDashboardSocket();

  useEffect(() => {
    let mounted = true;
    const load = () => {
      api
        .governanceTier()
        .then((t) => mounted && setTier(t))
        .catch(() => {});
    };
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (lastDelta?.scope === "tier") {
      api
        .governanceTier()
        .then(setTier)
        .catch(() => {});
    }
  }, [lastDelta]);

  if (!tier) {
    return (
      <Badge variant="outline" className="gap-1.5 text-xs">
        <span className="size-1.5 rounded-full bg-muted-foreground animate-pulse" />
        Tier —
      </Badge>
    );
  }

  const config = TIER_CONFIG[tier.tier] ?? TIER_CONFIG["1"];

  return (
    <Tooltip>
      <TooltipTrigger className="cursor-help">
        <Badge
          variant={config.variant}
          className="gap-1.5 text-xs select-none"
        >
          <Shield className="size-3 shrink-0" />
          <span
            className={cn("size-1.5 rounded-full shrink-0", config.dot)}
          />
          {config.label}
          {tier.shadow_mode && " · Shadow"}
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-xs">
        {tier.manual_mode
          ? "Tier 3 — manual SOP mode, automated dispatch & promotion disabled"
          : tier.tier === "2"
            ? "Tier 2 — greedy fallback only, MILP/ML pipeline unavailable"
            : "Tier 1 — full MILP + ML pipeline active"}
        {tier.shadow_mode
          ? " · Shadow mode: approvals are logged but not dispatched"
          : ""}
      </TooltipContent>
    </Tooltip>
  );
}
