"use client";

import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, Info, MousePointerClick } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import type { ActionCard } from "@/lib/types";
import { cn } from "@/lib/utils";

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
      <div className="p-5 space-y-4 animate-in fade-in-0 duration-200">
        <div className="space-y-2">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-4 w-1/4" />
        </div>
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
        <div className="flex gap-2">
          <Skeleton className="h-9 flex-1" />
          <Skeleton className="h-9 flex-1" />
        </div>
      </div>
    );
  }

  if (!card) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center animate-in fade-in-0 duration-300">
        <div className="rounded-full bg-muted p-4 ring-1 ring-border">
          <MousePointerClick className="size-7 text-muted-foreground" />
        </div>
        <div>
          <p className="font-medium text-sm">No event selected</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Select an event from the queue to view its action card.
          </p>
        </div>
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
    <Card className="border-0 rounded-none h-full flex flex-col">
      <CardHeader className="pb-3 shrink-0">
        {/* Event ID + status */}
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span className="font-mono font-semibold">{card.event_id}</span>
          <Badge variant="outline" className="text-xs">
            {card.status}
          </Badge>
        </CardTitle>

        {/* Tier 3 alert banner */}
        {tier3 && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/8 px-3 py-2 text-xs text-destructive mt-2">
            <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
            <p>
              <strong>Tier 3 — Continuity SOP mode.</strong> Approve/reject is
              audit-only; automated dispatch is disabled.
            </p>
          </div>
        )}

        {/* Tier 2 note */}
        {tier2 && !tier3 && (
          <div className="flex items-start gap-2 rounded-md border border-warn/40 bg-warn/8 px-3 py-2 text-xs text-warn mt-2">
            <Info className="size-3.5 shrink-0 mt-0.5" />
            <p>
              <strong>Tier 2</strong> — GREEDY_FALLBACK (static forecast). MILP/ML
              unavailable.
            </p>
          </div>
        )}
      </CardHeader>

      <ScrollArea className="flex-1 min-h-0">
        <CardContent className="pb-4">
          <Tabs defaultValue="impact">
            <TabsList className="w-full grid grid-cols-4 h-8">
              <TabsTrigger value="impact" className="text-xs">Impact</TabsTrigger>
              <TabsTrigger value="propagation" className="text-xs">Cascade</TabsTrigger>
              <TabsTrigger value="diversions" className="text-xs">Routes</TabsTrigger>
              <TabsTrigger value="evidence" className="text-xs">Evidence</TabsTrigger>
            </TabsList>

            <TabsContent value="impact" className="space-y-2 mt-3">
              {/* RCI progress bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Road Criticality Index</span>
                  <span className="font-mono font-medium">
                    {card.impact.rci.toFixed(2)}
                  </span>
                </div>
                <Progress
                  value={card.impact.rci * 100}
                  className="h-1.5"
                />
              </div>

              {/* P(closure) progress bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">P(closure)</span>
                  <span className="font-mono font-medium">
                    {card.impact.p_closure.toFixed(2)}
                  </span>
                </div>
                <Progress
                  value={card.impact.p_closure * 100}
                  className="h-1.5"
                />
              </div>

              <Separator />

              <Row label="Severity" value={card.impact.severity_band} />
              <Row
                label="ICT p50"
                value={`${card.impact.ict_p50_h.toFixed(1)} h`}
              />
            </TabsContent>

            <TabsContent value="propagation" className="space-y-2 mt-3">
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Cascade risk</span>
                  <span className="font-mono font-medium">
                    {card.propagation.cascade_risk.toFixed(2)}
                  </span>
                </div>
                <Progress
                  value={card.propagation.cascade_risk * 100}
                  className="h-1.5"
                />
              </div>
              <Separator />
              <Row
                label="Affected nodes"
                value={String(card.propagation.affected_nodes)}
              />
              <Row label="Max hop" value={String(card.propagation.max_hop)} />
            </TabsContent>

            <TabsContent value="diversions" className="space-y-2 mt-3">
              {card.diversions.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No diversion routes available.
                </p>
              ) : (
                card.diversions.map((route) => (
                  <div
                    key={route.rank}
                    className={cn(
                      "rounded-md border p-3 space-y-1",
                      "transition-colors hover:bg-accent/50"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-sm">
                        #{route.rank} {route.description}
                      </p>
                      <Badge variant="secondary" className="text-xs shrink-0">
                        {route.capacity_class}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      +{route.eta_delta_min.toFixed(1)} min ETA delta
                    </p>
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="evidence" className="space-y-2 mt-3">
              <Row
                label="Closure model"
                value={card.evidence.model_versions.closure}
              />
              <Row label="ICT model" value={card.evidence.model_versions.ict} />
              <Row label="Source" value={card.evidence.model_versions.source} />
            </TabsContent>
          </Tabs>

          {/* Action buttons */}
          <div className="flex gap-2 mt-5">
            {approveDisabled ? (
              <Tooltip>
                <TooltipTrigger render={<span className="flex-1" />}>
                  <Button
                    className="w-full pointer-events-none opacity-50"
                    aria-disabled="true"
                    tabIndex={-1}
                    variant="default"
                  >
                    <CheckCircle2 className="size-4 mr-1.5" />
                    Approve
                  </Button>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-xs">
                  {tier3
                    ? "Disabled — Tier 3 continuity mode, manual SOP only"
                    : "Disabled — shadow mode active, approvals are logged but not executed"}
                </TooltipContent>
              </Tooltip>
            ) : (
              <Button
                className="flex-1"
                onClick={handleApprove}
                disabled={submitting}
              >
                <CheckCircle2 className="size-4 mr-1.5" />
                Approve
              </Button>
            )}

            <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
              <DialogTrigger
                render={
                  <Button variant="outline" className="flex-1" />
                }
              >
                Reject
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reject {card.event_id}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="reason-code">Reason code</Label>
                    <Select value={reasonCode} onValueChange={(v) => v && setReasonCode(v)}>
                      <SelectTrigger id="reason-code">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {REJECT_REASON_CODES.map((code) => (
                          <SelectItem key={code} value={code}>
                            {code.replace(/_/g, " ")}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="override-notes">Override notes</Label>
                    <Textarea
                      id="override-notes"
                      rows={3}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Explain why this recommendation is being overridden…"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setRejectOpen(false)}
                    disabled={submitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleReject}
                    disabled={submitting}
                  >
                    {submitting ? "Submitting…" : "Confirm reject"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardContent>
      </ScrollArea>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-xs font-medium">{value}</span>
    </div>
  );
}
