"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { ActionCard } from "@/lib/types";

const COMMANDER_ID = "CMD-DASHBOARD";

const REJECT_REASON_CODES = [
  "MODEL_DISAGREE",
  "DUPLICATE_EVENT",
  "INSUFFICIENT_EVIDENCE",
  "RESOURCE_UNAVAILABLE",
];

interface ActionCardPanelProps {
  card: ActionCard | null;
  loading: boolean;
  onMutated: () => void;
}

export function ActionCardPanel({ card, loading, onMutated }: ActionCardPanelProps) {
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reasonCode, setReasonCode] = useState(REJECT_REASON_CODES[0]);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return (
      <div className="p-4 space-y-2">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (!card) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        Select an event from the queue to view its action card.
      </div>
    );
  }

  const tier2 = card.governance.tier === "2";
  const tier3 = card.governance.tier === "3" || card.governance.manual_mode;
  const approveDisabled = card.governance.shadow_mode || tier3;

  async function handleApprove() {
    setSubmitting(true);
    try {
      const result = await api.approve(card!.card_id, COMMANDER_ID);
      toast.success(result.message);
      onMutated();
    } catch {
      toast.error("Approve failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReject() {
    setSubmitting(true);
    try {
      const result = await api.reject(card!.card_id, COMMANDER_ID, reasonCode, notes);
      toast.success(result.message);
      setRejectOpen(false);
      setNotes("");
      onMutated();
    } catch {
      toast.error("Reject failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="border-0 rounded-none h-full overflow-y-auto">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2 text-base">
          <span>{card.event_id}</span>
          <Badge variant="outline">{card.status}</Badge>
        </CardTitle>
        {tier3 && (
          <Card className="border-destructive bg-destructive/5 mt-2">
            <CardContent className="py-2 text-xs text-destructive">
              Tier 3 — continuity SOP mode. Approve/reject is audit-only; dispatch is disabled.
            </CardContent>
          </Card>
        )}
        {tier2 && !tier3 && (
          <Badge variant="secondary" className="w-fit mt-2">
            GREEDY_FALLBACK (static forecast) — MILP/ML unavailable in Tier 2
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="impact">
          <TabsList className="w-full">
            <TabsTrigger value="impact">Impact</TabsTrigger>
            <TabsTrigger value="propagation">Propagation</TabsTrigger>
            <TabsTrigger value="diversions">Diversions</TabsTrigger>
            <TabsTrigger value="evidence">Evidence</TabsTrigger>
          </TabsList>
          <TabsContent value="impact" className="text-sm space-y-1">
            <Row label="RCI" value={card.impact.rci.toFixed(2)} />
            <Row label="P(closure)" value={card.impact.p_closure.toFixed(2)} />
            <Row label="Severity" value={card.impact.severity_band} />
            <Row label="ICT p50 (h)" value={card.impact.ict_p50_h.toFixed(1)} />
          </TabsContent>
          <TabsContent value="propagation" className="text-sm space-y-1">
            <Row label="Cascade risk" value={card.propagation.cascade_risk.toFixed(2)} />
            <Row label="Affected nodes" value={String(card.propagation.affected_nodes)} />
            <Row label="Max hop" value={String(card.propagation.max_hop)} />
          </TabsContent>
          <TabsContent value="diversions" className="text-sm space-y-2">
            {card.diversions.length === 0 && (
              <p className="text-muted-foreground">No diversion routes</p>
            )}
            {card.diversions.map((route) => (
              <div key={route.rank} className="border rounded p-2">
                <p className="font-medium">
                  #{route.rank} {route.description}
                </p>
                <p className="text-muted-foreground">
                  +{route.eta_delta_min.toFixed(1)} min · {route.capacity_class} capacity
                </p>
              </div>
            ))}
          </TabsContent>
          <TabsContent value="evidence" className="text-sm space-y-1">
            <Row label="Closure model" value={card.evidence.model_versions.closure} />
            <Row label="ICT model" value={card.evidence.model_versions.ict} />
            <Row label="Source" value={card.evidence.model_versions.source} />
          </TabsContent>
        </Tabs>

        <div className="flex gap-2 mt-4">
          {approveDisabled ? (
            <Tooltip>
              <TooltipTrigger render={<span className="w-full" />}>
                <Button
                  className="w-full pointer-events-none"
                  aria-disabled="true"
                  tabIndex={-1}
                >
                  Approve
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {tier3
                  ? "Disabled — Tier 3 continuity mode, manual SOP only"
                  : "Disabled — shadow mode active, approvals are logged but not executed"}
              </TooltipContent>
            </Tooltip>
          ) : (
            <Button className="w-full" onClick={handleApprove} disabled={submitting}>
              Approve
            </Button>
          )}

          <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
            <DialogTrigger render={<Button variant="outline" className="w-full" />}>
              Reject
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Reject {card.event_id}</DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium">Reason code</label>
                  <select
                    className="w-full border rounded-md p-2 text-sm mt-1"
                    value={reasonCode}
                    onChange={(e) => setReasonCode(e.target.value)}
                  >
                    {REJECT_REASON_CODES.map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium">Override notes</label>
                  <textarea
                    className="w-full border rounded-md p-2 text-sm mt-1"
                    rows={3}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Explain why this recommendation is being overridden"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button onClick={handleReject} disabled={submitting}>
                  Confirm reject
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}
