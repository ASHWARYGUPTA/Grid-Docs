"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertQueue } from "./_components/alert-queue";
import { MapPanel } from "./_components/map-panel";
import { ActionCardPanel } from "./_components/action-card-panel";
import { api } from "@/lib/api";
import { useDashboardSocket } from "@/lib/ws";
import type { ActionCard, QueueItem } from "@/lib/types";

const QUEUE_POLL_MS = 15_000;

export default function LivePage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [card, setCard] = useState<ActionCard | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const { lastDelta } = useDashboardSocket();

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
    <div className="grid grid-cols-[320px_1fr_360px] h-[calc(100vh-3.5rem)]">
      <div className="border-r overflow-y-auto">
        <AlertQueue items={items} selectedEventId={selectedEventId} onSelect={setSelectedEventId} />
      </div>
      <div className="relative">
        <MapPanel selectedCard={card} />
      </div>
      <div className="border-l overflow-y-auto">
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
  );
}
