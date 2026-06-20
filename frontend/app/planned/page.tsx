"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import type { PlannedEventPackage } from "@/lib/types";

export default function PlannedPage() {
  const [packages, setPackages] = useState<PlannedEventPackage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .plannedUpcoming(72)
      .then(setPackages)
      .catch(() => setPackages([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      <h1 className="text-lg font-semibold">Planned events — next 72h</h1>
      {loading && <p className="text-muted-foreground text-sm">Loading…</p>}
      {!loading && packages.length === 0 && (
        <p className="text-muted-foreground text-sm">No planned events in the next 72 hours.</p>
      )}
      {packages.map((pkg) => (
        <Card key={pkg.event_id}>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span>
                {pkg.corridor ?? "Non-corridor"} — {pkg.cause}
              </span>
              <Badge variant={pkg.low_confidence_template ? "secondary" : "outline"}>
                {pkg.hours_until_start.toFixed(1)}h until start
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-2">
            <div className="flex justify-between text-muted-foreground">
              <span>Staffing</span>
              <span>
                {pkg.staffing_min}–{pkg.staffing_max}
              </span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>Barricades</span>
              <span>
                {pkg.barricade_count} {pkg.barricade_staging_required ? "(staging required)" : ""}
              </span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>RCI / P(closure)</span>
              <span>
                {pkg.impact_overlay.rci.toFixed(2)} / {pkg.impact_overlay.p_closure.toFixed(2)}
              </span>
            </div>
            <Separator />
            <div>
              <p className="font-medium mb-1">Checklist</p>
              <ul className="space-y-0.5">
                {pkg.checklist.map((item) => (
                  <li key={item.id} className="flex items-center gap-2">
                    <Badge variant={item.required ? "default" : "outline"} className="shrink-0">
                      {item.category}
                    </Badge>
                    <span>{item.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
