"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useDashboardSocket } from "@/lib/ws";
import type { GovernanceTierResponse } from "@/lib/types";

const TIER_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  "1": "default",
  "2": "secondary",
  "3": "destructive",
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
    return <Badge variant="outline">Tier —</Badge>;
  }

  return (
    <div className="flex items-center gap-2">
      <Tooltip>
        <TooltipTrigger
          render={<Badge variant={TIER_VARIANT[tier.tier] ?? "outline"} />}
        >
          Tier {tier.tier}
          {tier.shadow_mode ? " · Shadow" : ""}
        </TooltipTrigger>
        <TooltipContent>
          {tier.manual_mode
            ? "Tier 3 — manual SOP mode, automated dispatch/promotion disabled"
            : tier.tier === "2"
              ? "Tier 2 — greedy fallback only, MILP/ML untrustworthy"
              : "Tier 1 — full MILP + ML pipeline active"}
          {tier.shadow_mode ? " (shadow mode: approvals logged, not executed)" : ""}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
