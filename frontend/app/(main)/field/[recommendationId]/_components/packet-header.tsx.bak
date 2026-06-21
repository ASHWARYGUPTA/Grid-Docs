"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FieldPacket, Tier } from "@/lib/types";

interface PacketHeaderProps {
  packet: FieldPacket;
  liveTier: Tier | null;
  acking: boolean;
  onAck: () => void;
}

export function PacketHeader({ packet, liveTier, acking, onAck }: PacketHeaderProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <span>{packet.recommendation_id}</span>
          <Badge variant={packet.source === "MILP" ? "default" : "secondary"}>
            {packet.source}
          </Badge>
          <Badge variant="outline">Tier at decision: {packet.tier_at_decision}</Badge>
          {liveTier && liveTier !== packet.tier_at_decision && (
            <Badge variant="outline">Now: Tier {liveTier}</Badge>
          )}
          {packet.acknowledged && <Badge variant="default">Acknowledged</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {packet.already_closed && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
            This event is already closed.
          </div>
        )}
        <div className="text-sm text-muted-foreground">
          Event <span className="font-medium text-foreground">{packet.event_id}</span> — status{" "}
          {packet.event_status}
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {Object.entries(packet.provenance).map(([key, value]) => (
            <span key={key} className="rounded border px-1.5 py-0.5">
              {key}: {value}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={packet.navigation_deep_link} target="_blank" rel="noreferrer">
            <Button variant="outline">Open navigation</Button>
          </a>
          {!packet.acknowledged && (
            <Button onClick={onAck} disabled={acking}>
              {acking ? "Acknowledging…" : "Acknowledge"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
