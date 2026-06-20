"use client";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { QueueItem } from "@/lib/types";

const PRIORITY_VARIANT: Record<string, "destructive" | "default" | "secondary" | "outline"> = {
  CRITICAL: "destructive",
  HIGH: "default",
  MEDIUM: "secondary",
  LOW: "outline",
};

interface AlertQueueProps {
  items: QueueItem[];
  selectedEventId: string | null;
  onSelect: (eventId: string) => void;
}

export function AlertQueue({ items, selectedEventId, onSelect }: AlertQueueProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Priority</TableHead>
          <TableHead>Corridor</TableHead>
          <TableHead className="text-right">RCI</TableHead>
          <TableHead className="text-right">P(closure)</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow
            key={item.event_id}
            data-state={item.event_id === selectedEventId ? "selected" : undefined}
            className="cursor-pointer"
            onClick={() => onSelect(item.event_id)}
          >
            <TableCell>
              <Badge variant={PRIORITY_VARIANT[item.alert_priority] ?? "outline"}>
                {item.alert_priority}
              </Badge>
            </TableCell>
            <TableCell className="text-sm">{item.corridor ?? "Non-corridor"}</TableCell>
            <TableCell className="text-right font-mono text-sm">{item.rci.toFixed(2)}</TableCell>
            <TableCell className="text-right font-mono text-sm">
              {item.p_closure.toFixed(2)}
            </TableCell>
          </TableRow>
        ))}
        {items.length === 0 && (
          <TableRow>
            <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
              No active events
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
