"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertQueue } from "./_components/alert-queue";
import { MapPanel } from "./_components/map-panel";
import { ActionCardPanel } from "./_components/action-card-panel";
import { AppHeader } from "@/components/app-header";
import { api } from "@/lib/api";
import { useDashboardSocket } from "@/lib/ws";
import type { ActionCard, QueueItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { InfoPopover } from "@/components/info-popover";

const QUEUE_POLL_MS = 15_000;

export default function LivePage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [card, setCard] = useState<ActionCard | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const { lastDelta, connected } = useDashboardSocket();

  const loadQueue = useCallback(() => {
    api
      .queue()
      .then((res) => setItems(res.items))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadQueue();
    const interval = setInterval(loadQueue, QUEUE_POLL_MS);
    return () => clearInterval(interval);
  }, [loadQueue]);

  // Tracks the most recently requested event so a slower, earlier request
  // can't overwrite the card after a later selection's response already won.
  const latestRequestedEventId = useRef<string | null>(null);

  const loadCard = useCallback((eventId: string) => {
    latestRequestedEventId.current = eventId;
    Promise.resolve().then(() => setCardLoading(true));
    api
      .card(eventId)
      .then((res) => {
        if (latestRequestedEventId.current === eventId) setCard(res);
      })
      .catch(() => {
        if (latestRequestedEventId.current === eventId) setCard(null);
      })
      .finally(() => {
        if (latestRequestedEventId.current === eventId) setCardLoading(false);
      });
  }, []);

  useEffect(() => {
    if (selectedEventId) loadCard(selectedEventId);
  }, [selectedEventId, loadCard]);

  // Patch the queue + selected card in place when a matching delta arrives,
  // rather than refetching everything.
  useEffect(() => {
    if (!lastDelta) return;
    if (lastDelta.scope === "card" || lastDelta.scope === "hotspot") {
      loadQueue();
    }
    if (lastDelta.scope === "card" && selectedEventId && lastDelta.event_id === selectedEventId) {
      loadCard(selectedEventId);
    }
  }, [lastDelta, selectedEventId, loadQueue, loadCard]);

  return (
    <div className="flex flex-col h-[calc(100svh-0px)] overflow-hidden">
      <AppHeader title="Live Monitor">
        {/* WebSocket status indicator */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            className={cn(
              "size-1.5 rounded-full",
              connected ? "bg-live animate-live" : "bg-muted-foreground"
            )}
          />
          <span>{connected ? "Live" : "Reconnecting…"}</span>
        </div>
      </AppHeader>

      {/* Three-column layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Column 1 — Alert queue */}
        <div id="tour-alert-queue" className="w-[300px] shrink-0 border-r flex flex-col overflow-hidden">
          <AlertQueue
            items={items}
            selectedEventId={selectedEventId}
            onSelect={setSelectedEventId}
          />
        </div>

        {/* Column 2 — Map */}
        <div id="tour-live-map" className="flex-1 relative overflow-hidden">
          <MapPanel selectedCard={card} />
        </div>

        {/* Column 3 — Action card */}
        <div id="tour-action-card" className="w-[340px] shrink-0 border-l flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold">Action Card</span>
              <InfoPopover
                title="Action Card"
                description="Shows the AI-generated dispatch recommendation for the selected alert. Review the suggested routes, resource allocation, and confidence score before approving or rejecting."
                side="left"
              />
            </div>
            {card && (
              <span className="text-xs text-muted-foreground font-mono">
                {card.card_id}
              </span>
            )}
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            <ActionCardPanel
              card={card}
              loading={cardLoading}
              onMutated={() => {
                loadQueue();
                if (selectedEventId) loadCard(selectedEventId);
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
