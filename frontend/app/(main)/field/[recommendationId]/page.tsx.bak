"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { cachePacket, drainQueue, readCachedPacket } from "@/lib/field-offline-queue";
import type { FieldPacket, Tier } from "@/lib/types";
import { ClosureForm } from "./_components/closure-form";
import { DiversionPanel } from "./_components/diversion-panel";
import { IctPanel } from "./_components/ict-panel";
import { PacketHeader } from "./_components/packet-header";

export default function FieldPacketPage() {
  const params = useParams<{ recommendationId: string }>();
  const recommendationId = params.recommendationId;

  const [packet, setPacket] = useState<FieldPacket | null>(null);
  const [usingCache, setUsingCache] = useState(false);
  const [liveTier, setLiveTier] = useState<Tier | null>(null);
  const [loading, setLoading] = useState(true);
  const [acking, setAcking] = useState(false);

  const loadPacket = useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await api.fieldPacket(recommendationId);
      setPacket(fresh);
      setUsingCache(false);
      cachePacket(recommendationId, fresh);
    } catch {
      const cached = readCachedPacket(recommendationId);
      if (cached) {
        setPacket(cached);
        setUsingCache(true);
      } else {
        toast.error("Could not load assignment packet");
      }
    } finally {
      setLoading(false);
    }
  }, [recommendationId]);

  useEffect(() => {
    loadPacket();
    api
      .fieldTier()
      .then((res) => setLiveTier(res.tier))
      .catch(() => setLiveTier(null));
  }, [loadPacket]);

  useEffect(() => {
    function onOnline() {
      drainQueue().then(({ synced }) => {
        if (synced > 0) toast.success(`Synced ${synced} queued closure(s)`);
      });
    }
    drainQueue().then(({ synced }) => {
      if (synced > 0) toast.success(`Synced ${synced} queued closure(s)`);
    });
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, []);

  async function handleAck() {
    setAcking(true);
    try {
      await api.fieldAck(recommendationId, "OFFICER-FIELD-APP");
      toast.success("Acknowledged");
      await loadPacket();
    } catch {
      toast.error("Failed to acknowledge");
    } finally {
      setAcking(false);
    }
  }

  if (loading && !packet) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (!packet) {
    return (
      <div className="p-6 max-w-2xl mx-auto text-sm text-muted-foreground">
        Assignment packet not found.
      </div>
    );
  }

  if (liveTier === "3") {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <div className="rounded-md border p-4 text-sm">
          Tier 3 — manual mode. Refer to station SOP for procedure.
        </div>
        <ClosureForm
          eventId={packet.event_id}
          alreadyClosed={packet.already_closed}
          onClosed={loadPacket}
        />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-4">
      {usingCache && (
        <div className="rounded-md border border-secondary bg-secondary/30 p-2 text-sm">
          Showing cached data — may be stale.
        </div>
      )}
      <PacketHeader packet={packet} liveTier={liveTier} acking={acking} onAck={handleAck} />
      <IctPanel impact={packet.impact} liveTier={liveTier} />
      <DiversionPanel diversion={packet.top_diversion} liveTier={liveTier} />
      <ClosureForm
        eventId={packet.event_id}
        alreadyClosed={packet.already_closed}
        onClosed={loadPacket}
      />
    </div>
  );
}
