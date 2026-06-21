"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FieldDiversionSummary, Tier } from "@/lib/types";

interface DiversionPanelProps {
  diversion: FieldDiversionSummary | null;
  liveTier: Tier | null;
}

export function DiversionPanel({ diversion, liveTier }: DiversionPanelProps) {
  if (!diversion) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Diversion</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          No diversion route available for this event.
        </CardContent>
      </Card>
    );
  }

  const simplified = liveTier === "2";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Top diversion</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p>{diversion.route_summary}</p>
        {!simplified && (
          <>
            <div className="flex justify-between text-muted-foreground">
              <span>Junction</span>
              <span>{diversion.junction_id}</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>ETA delta</span>
              <span>{diversion.eta_delta_min.toFixed(1)} min</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>Capacity</span>
              <span>{diversion.capacity_class}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
