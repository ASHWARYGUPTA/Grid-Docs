"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FieldIctBands, Tier } from "@/lib/types";

const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  Green: "outline",
  Yellow: "secondary",
  Orange: "default",
  Red: "destructive",
};

interface IctPanelProps {
  impact: FieldIctBands;
  liveTier: Tier | null;
}

export function IctPanel({ impact, liveTier }: IctPanelProps) {
  const cached = liveTier === "2";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>Incident clearance time</span>
          <div className="flex items-center gap-2">
            {cached && <Badge variant="secondary">cached bands</Badge>}
            <Badge variant={SEVERITY_VARIANT[impact.severity_band] ?? "outline"}>
              {impact.severity_band}
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-3 text-center text-sm">
          <div>
            <div className="text-muted-foreground">P20</div>
            <div className="text-lg font-semibold">{impact.ict_p20_h.toFixed(1)}h</div>
          </div>
          <div>
            <div className="text-muted-foreground">P50</div>
            <div className="text-lg font-semibold">{impact.ict_p50_h.toFixed(1)}h</div>
          </div>
          <div>
            <div className="text-muted-foreground">P80</div>
            <div className="text-lg font-semibold">{impact.ict_p80_h.toFixed(1)}h</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
