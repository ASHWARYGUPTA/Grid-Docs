"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  History,
  Info,
  MousePointerClick,
  Sparkles,
} from "lucide-react";
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
import { enqueueClosure } from "@/lib/field-offline-queue";
import { validateClosure } from "@/app/field/[recommendationId]/_components/closure-form";
import type {
  ActionCard,
  CardStatus,
  ClosureRequest,
  LatestJobResponse,
  TransitImpactIndex,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const COMMANDER_ID = "CMD-DASHBOARD";

// "Close & Learn" is offered on cards whose event is still live (not rejected):
// closing re-ingests the event as `closed`, which feeds the M13 replay buffer.
export function canCloseAndLearn(status: CardStatus): boolean {
  return status === "complete" || status === "approved" || status === "executed";
}

// What we show after a closure so the operator can see the learning loop fire.
interface LearningSignal {
  queuedOffline: boolean;
  job: LatestJobResponse | null;
  bufferCount: number | null;
}

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
  // Cross-highlights a diversion route with its line on the map — fired on
  // hover/unhover of a route row; null clears the highlight.
  onHoverRoute?: (rank: number | null) => void;
}

export function ActionCardPanel({ card, loading, onMutated, onHoverRoute }: ActionCardPanelProps) {
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reasonCode, setReasonCode] = useState(REJECT_REASON_CODES[0]);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Tabs are controlled so the Transit panel can lazy-load on first open.
  const [activeTab, setActiveTab] = useState("impact");
  const [transit, setTransit] = useState<TransitImpactIndex | null>(null);
  const [transitState, setTransitState] = useState<"idle" | "loading" | "error">("idle");

  // Close & Learn dialog + resulting learning signal.
  const [closeOpen, setCloseOpen] = useState(false);
  const [barricadesUsed, setBarricadesUsed] = useState(0);
  const [officersUsed, setOfficersUsed] = useState(1);
  const [diversionActivated, setDiversionActivated] = useState(false);
  const [closeNotes, setCloseNotes] = useState("");
  const [closing, setClosing] = useState(false);
  const [learningSignal, setLearningSignal] = useState<LearningSignal | null>(null);

  const cardEventId = card?.event_id ?? null;

  // Reset per-card UI when the selected event changes.
  useEffect(() => {
    setActiveTab("impact");
    setTransit(null);
    setTransitState("idle");
    setCloseOpen(false);
    setLearningSignal(null);
  }, [cardEventId]);

  // Lazy-load M12 transit impact when the Transit tab is opened. Deps are kept to
  // [activeTab, cardEventId] only: adding transitState/transit would re-run the
  // effect the instant it flips to "loading", and that re-run's cleanup would
  // abandon the in-flight request (via `active`) before it ever resolves.
  useEffect(() => {
    if (activeTab !== "transit" || !cardEventId) return;
    let active = true;
    setTransitState("loading");
    api
      .transitImpact(cardEventId)
      .then((res) => {
        if (active) {
          setTransit(res);
          setTransitState("idle");
        }
      })
      .catch(() => {
        if (active) setTransitState("error");
      });
    return () => {
      active = false;
    };
  }, [activeTab, cardEventId]);

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

  // After a closure, pull the latest M13 retrain job + buffer size so the
  // commander can see the learning loop has been fed.
  async function surfaceLearningSignal(queuedOffline: boolean) {
    const job = await api.latestLearningJob().catch(() => null);
    let bufferCount: number | null = null;
    if (job) {
      const manifest = await api.learningManifest(job.job_id).catch(() => null);
      if (manifest) bufferCount = manifest.recent_count + manifest.anchor_count;
    }
    setLearningSignal({ queuedOffline, job, bufferCount });
  }

  async function handleClose() {
    const v = validateClosure(barricadesUsed, officersUsed);
    if (!v.valid) {
      toast.error(v.barricadesError ?? v.officersError ?? "Invalid closure input");
      return;
    }
    const request: ClosureRequest = {
      closed_datetime: new Date().toISOString(),
      barricades_used: barricadesUsed,
      officers_used: officersUsed,
      diversion_activated: diversionActivated,
      notes: closeNotes || null,
      officer_id: COMMANDER_ID,
    };
    setClosing(true);
    try {
      await api.fieldClose(card!.event_id, request);
      toast.success("Event closed — feeds the M13 replay buffer");
      setCloseOpen(false);
      onMutated();
      await surfaceLearningSignal(false);
    } catch {
      // Mirror the field app: never lose a closure — queue it for later sync.
      enqueueClosure(card!.event_id, request);
      toast.warning("Closure queued — will sync when back online");
      setCloseOpen(false);
      setLearningSignal({ queuedOffline: true, job: null, bufferCount: null });
    } finally {
      setClosing(false);
    }
  }

  const closeValidation = validateClosure(barricadesUsed, officersUsed);

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
          <Tabs value={activeTab} onValueChange={(v) => v && setActiveTab(v as string)}>
            <TabsList className="w-full grid grid-cols-5 h-8">
              <TabsTrigger value="impact" className="text-xs">Impact</TabsTrigger>
              <TabsTrigger value="propagation" className="text-xs">Cascade</TabsTrigger>
              <TabsTrigger value="diversions" className="text-xs">Routes</TabsTrigger>
              <TabsTrigger value="transit" className="text-xs">Transit</TabsTrigger>
              <TabsTrigger value="evidence" className="text-xs">Evidence</TabsTrigger>
            </TabsList>

            <TabsContent value="impact" className="space-y-2 mt-3">
              {/* RCI progress bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Road Criticality Index</span>
                  <span className="font-mono font-medium">
                    {(card.impact.rci * 100).toFixed(0)}%
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
                    {(card.impact.p_closure * 100).toFixed(0)}%
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
                    onMouseEnter={() => onHoverRoute?.(route.rank)}
                    onMouseLeave={() => onHoverRoute?.(null)}
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
                    {route.waypoints.length < 2 && (
                      <p className="text-[11px] text-muted-foreground italic">
                        Map geometry unavailable for this route.
                      </p>
                    )}
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="transit" className="space-y-2 mt-3">
              {transitState === "loading" && (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-16 w-full" />
                </div>
              )}
              {transitState === "error" && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Transit impact unavailable for this event.
                </p>
              )}
              {transitState === "idle" && transit && (
                <>
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">Passenger delay index</span>
                      <span className="font-mono font-medium">
                        {transit.passenger_delay_index.toFixed(2)}
                      </span>
                    </div>
                    <Progress
                      value={Math.min(transit.passenger_delay_index * 100, 100)}
                      className="h-1.5"
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">Transfer overload risk</span>
                      <span className="font-mono font-medium">
                        {transit.transfer_overload_risk.toFixed(2)}
                      </span>
                    </div>
                    <Progress
                      value={Math.min(transit.transfer_overload_risk * 100, 100)}
                      className="h-1.5"
                    />
                  </div>

                  <Separator />

                  {transit.advisory_message && (
                    <p className="text-xs text-muted-foreground">{transit.advisory_message}</p>
                  )}

                  {transit.affected_routes.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-2">
                      No affected BMTC routes.
                    </p>
                  ) : (
                    <div className="space-y-1.5">
                      <p className="text-xs text-muted-foreground">
                        Affected BMTC routes ({transit.affected_routes.length})
                      </p>
                      {transit.affected_routes.map((r) => (
                        <div key={r.route_id} className="rounded-md border p-2 space-y-0.5">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm font-medium">{r.name}</p>
                            <Badge variant="secondary" className="text-xs shrink-0">
                              +{r.predicted_delay_min.toFixed(0)} min
                            </Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            {(r.overlap_fraction * 100).toFixed(0)}% corridor overlap · occupancy{" "}
                            {r.occupancy}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {transit.advisory_only && (
                    <p className="text-[11px] text-muted-foreground italic">
                      Advisory only — not an enforcement action.
                    </p>
                  )}
                </>
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

          {/* Close & Learn — commander-side closure that feeds the M13 buffer */}
          {canCloseAndLearn(card.status) && (
            <Dialog open={closeOpen} onOpenChange={setCloseOpen}>
              <DialogTrigger
                render={<Button variant="outline" className="w-full mt-2 gap-1.5" />}
              >
                <History className="size-4" />
                Close &amp; Learn
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Close {card.event_id}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <p className="text-xs text-muted-foreground">
                    Closing re-ingests this event as{" "}
                    <span className="font-mono">closed</span> and feeds the M13
                    replay buffer used for the next retrain.
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="close-barricades">Barricades used</Label>
                      <input
                        id="close-barricades"
                        type="number"
                        min={0}
                        step={1}
                        value={barricadesUsed}
                        onChange={(e) => setBarricadesUsed(Number(e.target.value))}
                        className="w-full rounded-md border bg-transparent px-3 py-1.5 text-sm"
                      />
                      {closeValidation.barricadesError && (
                        <p className="text-xs text-destructive">
                          {closeValidation.barricadesError}
                        </p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="close-officers">Officers used</Label>
                      <input
                        id="close-officers"
                        type="number"
                        min={1}
                        step={1}
                        value={officersUsed}
                        onChange={(e) => setOfficersUsed(Number(e.target.value))}
                        className="w-full rounded-md border bg-transparent px-3 py-1.5 text-sm"
                      />
                      {closeValidation.officersError && (
                        <p className="text-xs text-destructive">
                          {closeValidation.officersError}
                        </p>
                      )}
                    </div>
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={diversionActivated}
                      onChange={(e) => setDiversionActivated(e.target.checked)}
                    />
                    Diversion activated
                  </label>
                  <div className="space-y-1.5">
                    <Label htmlFor="close-notes">Notes</Label>
                    <Textarea
                      id="close-notes"
                      rows={3}
                      value={closeNotes}
                      onChange={(e) => setCloseNotes(e.target.value)}
                      placeholder="Closure context for the learning loop…"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setCloseOpen(false)}
                    disabled={closing}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleClose}
                    disabled={closing || !closeValidation.valid}
                  >
                    {closing ? "Closing…" : "Confirm closure"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* Learning-loop signal after a successful (or queued) closure */}
          {learningSignal && (
            <div className="mt-4 rounded-md border border-primary/20 bg-primary/5 px-3 py-2.5 space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium">
                <Sparkles className="size-3.5 text-primary" />
                Learning loop
              </div>
              {learningSignal.queuedOffline ? (
                <p className="text-xs text-muted-foreground">
                  Closure queued offline — it will feed the M13 replay buffer once it
                  syncs.
                </p>
              ) : (
                <>
                  <p className="text-xs text-muted-foreground">
                    Closure recorded. This event now feeds the M13 replay buffer for the
                    next retrain.
                  </p>
                  {learningSignal.job ? (
                    <div className="space-y-0.5">
                      <Row label="Latest retrain job" value={learningSignal.job.job_id} />
                      <Row label="Job status" value={learningSignal.job.status} />
                      {learningSignal.bufferCount != null && (
                        <Row
                          label="Buffer samples"
                          value={String(learningSignal.bufferCount)}
                        />
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      No retrain job has run yet.
                    </p>
                  )}
                </>
              )}
            </div>
          )}
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
