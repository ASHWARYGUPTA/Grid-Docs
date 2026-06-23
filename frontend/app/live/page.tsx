"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DashboardTable } from "./_components/dashboard-table";
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
  const [selectedPredictedCorridor, setSelectedPredictedCorridor] = useState<{lat: number, lng: number} | null>(null);
  const [activeTab, setActiveTab] = useState("outline");
  const [card, setCard] = useState<ActionCard | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [highlightedRouteRank, setHighlightedRouteRank] = useState<number | null>(null);
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
    setHighlightedRouteRank(null);
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

      {/* Dashboard Layout */}
      <div className="flex-1 min-h-0 overflow-auto bg-muted/20 p-4 sm:p-6 space-y-6">
        {/* Map Section */}
        <div id="tour-live-map" className="h-[45vh] min-h-[350px] w-full border rounded-xl overflow-hidden shadow-sm bg-card relative">
          <MapPanel
            selectedCard={card}
            onSelectEvent={setSelectedEventId}
            highlightedRouteRank={highlightedRouteRank}
            activeDashboardTab={activeTab}
            selectedPredictedCorridor={selectedPredictedCorridor}
          />
        </div>

        {/* Table Section */}
        <div id="tour-alert-queue" className="flex-1">
          <DashboardTable
            items={items}
            selectedEventId={selectedEventId}
            onSelect={setSelectedEventId}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            onSelectPredicted={setSelectedPredictedCorridor}
            card={card}
            cardLoading={cardLoading}
            onMutated={() => {
              loadQueue();
              if (selectedEventId) loadCard(selectedEventId);
            }}
            onHoverRoute={setHighlightedRouteRank}
          />
        </div>
      </div>
    </div>
  );
}
