"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { can } from "@/lib/auth";
import {
  AlertOctagon,
  AlertTriangle,
  CalendarClock,
  CalendarX,
  ChevronDown,
  ChevronUp,
  Clock,
  Filter,
  History,
  MapPin,
  Music,
  Plus,
  RefreshCw,
  Route,
  Shield,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Users,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { StatCard } from "@/components/stat-card";
import { InfoPopover } from "@/components/info-popover";
import { api } from "@/lib/api";
import type {
  AnalogEvent,
  CorridorCentroid,
  HotspotCluster,
  PlannedEventPackage,
  PlannedIngestPayload,
} from "@/lib/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CAUSE_LABELS: Record<string, string> = {
  construction: "Construction",
  vip_movement: "VIP Movement",
  procession: "Procession",
  public_event: "Public Event",
  protest: "Protest",
};

const CAUSE_ICONS: Record<string, React.ElementType> = {
  construction: Wrench,
  vip_movement: Shield,
  procession: Users,
  public_event: Music,
  protest: AlertOctagon,
};

// Coordinates come from the real corridor_centroids table via GET /api/v1/corridors
// (M17, mean lat/lon per corridor from the ASTraM CSV). The Bengaluru city centre
// is used only when the operator's corridor can't be matched to a real centroid.
const DEFAULT_COORDS: [number, number] = [12.9716, 77.5946]; // Bengaluru centroid

export function resolveCorridorCoords(
  corridor: string | null,
  centroids: CorridorCentroid[],
): [number, number] {
  if (!corridor) return DEFAULT_COORDS;
  const q = corridor.trim().toLowerCase();
  if (!q) return DEFAULT_COORDS;
  const exact = centroids.find((c) => c.name.toLowerCase() === q);
  if (exact) return [exact.lat, exact.lon];
  const fuzzy = centroids.find(
    (c) => c.name.toLowerCase().includes(q) || q.includes(c.name.toLowerCase()),
  );
  if (fuzzy) return [fuzzy.lat, fuzzy.lon];
  return DEFAULT_COORDS;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type UrgencyLevel = "critical" | "high" | "medium" | "normal";

function urgencyLevel(pkg: PlannedEventPackage): UrgencyLevel {
  if (pkg.hours_until_start <= pkg.deployment_lead_time_hours) return "critical";
  if (pkg.hours_until_start < 6) return "high";
  if (pkg.hours_until_start < 24) return "medium";
  return "normal";
}

const URGENCY_STYLES: Record<UrgencyLevel, { border: string; badge: string; label: string }> = {
  critical: { border: "border-l-destructive", badge: "bg-destructive/10 text-destructive border-destructive/30", label: "Deploy Now" },
  high:     { border: "border-l-destructive", badge: "bg-destructive/10 text-destructive border-destructive/30", label: "< 6h" },
  medium:   { border: "border-l-warn",        badge: "bg-warn/10 text-warn border-warn/30",                     label: "< 24h" },
  normal:   { border: "border-l-primary/40",  badge: "bg-primary/8 text-primary border-primary/20",             label: "" },
};

const SEVERITY_BADGE: Record<string, string> = {
  Red:    "bg-destructive/10 text-destructive border-destructive/30",
  Orange: "bg-warn/10 text-warn border-warn/30",
  Yellow: "bg-yellow-500/10 text-yellow-600 border-yellow-400/30",
  Green:  "bg-live/10 text-live border-live/30",
};

// ---------------------------------------------------------------------------
// Event Card
// ---------------------------------------------------------------------------

function EventCard({ pkg, onEdit, canEdit = true }: { pkg: PlannedEventPackage; onEdit: (pkg: PlannedEventPackage) => void; canEdit?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [showAnalogs, setShowAnalogs] = useState(false);
  const level = urgencyLevel(pkg);
  const style = URGENCY_STYLES[level];
  const label = style.label || `${pkg.hours_until_start.toFixed(0)}h away`;
  const impact = pkg.impact_overlay;
  const CauseIcon = CAUSE_ICONS[pkg.cause] ?? CalendarClock;

  return (
    <Card className={cn("border-l-4 transition-shadow duration-200 hover:shadow-md", style.border)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-start justify-between gap-3 text-sm font-semibold">
          <span className="leading-snug flex items-center gap-1.5">
            <CauseIcon className="size-3.5 shrink-0 text-muted-foreground" />
            {pkg.corridor ?? "Non-corridor"} — {CAUSE_LABELS[pkg.cause] ?? pkg.cause}
          </span>
          <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
            {pkg.low_confidence_template && (
              <Badge variant="outline" className="gap-1 text-[10px] bg-warn/10 text-warn border-warn/30">
                <AlertTriangle className="size-2.5" />
                Low confidence
              </Badge>
            )}
            <Badge variant="outline" className={cn("gap-1 text-[10px]", SEVERITY_BADGE[impact.severity_band] ?? "bg-muted text-muted-foreground")}>
              {impact.severity_band}
            </Badge>
            <Badge variant="outline" className={cn("gap-1 text-[10px]", style.badge)}>
              <Clock className="size-2.5" />
              {label}
            </Badge>
          </div>
        </CardTitle>

        {level === "critical" && (
          <div className="flex items-center gap-1.5 text-xs text-destructive font-medium mt-1">
            <ShieldAlert className="size-3.5 shrink-0" />
            Deployment window closing — lead time is {pkg.deployment_lead_time_hours}h, event starts in {pkg.hours_until_start.toFixed(1)}h
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-3 text-sm">
        {/* Metrics */}
        <div className="grid grid-cols-4 gap-2">
          <div className="rounded-md bg-muted/60 px-2 py-2 text-center">
            <p className="text-[10px] text-muted-foreground mb-0.5">Staffing</p>
            <p className="font-semibold tabular-nums text-xs">{pkg.staffing_min}–{pkg.staffing_max}</p>
          </div>
          <div className="rounded-md bg-muted/60 px-2 py-2 text-center">
            <p className="text-[10px] text-muted-foreground mb-0.5">Barricades</p>
            <p className="font-semibold tabular-nums text-xs">{pkg.barricade_count}</p>
          </div>
          <div className="rounded-md bg-muted/60 px-2 py-2 text-center">
            <p className="text-[10px] text-muted-foreground mb-0.5">P(closure)</p>
            <p className={cn("font-semibold tabular-nums text-xs", impact.p_closure > 0.7 ? "text-destructive" : impact.p_closure > 0.4 ? "text-warn" : "")}>
              {(impact.p_closure * 100).toFixed(0)}%
            </p>
          </div>
          <div className="rounded-md bg-muted/60 px-2 py-2 text-center">
            <p className="text-[10px] text-muted-foreground mb-0.5">ICT p50</p>
            <p className="font-semibold tabular-nums text-xs">{impact.ict_p50_h.toFixed(1)}h</p>
          </div>
        </div>

        {/* Warnings */}
        <div className="flex flex-wrap gap-2">
          {pkg.barricade_staging_required && (
            <p className="text-xs text-warn flex items-center gap-1">
              <AlertTriangle className="size-3" />
              Barricade staging required
            </p>
          )}
          {pkg.estimated_duration_h != null && (
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="size-3" />
              Est. duration: {pkg.estimated_duration_h.toFixed(1)}h
            </p>
          )}
        </div>

        {/* Analog events (historical precedents) */}
        {pkg.analog_events && pkg.analog_events.length > 0 && (
          <>
            <Separator />
            <button
              className="flex w-full items-center justify-between text-xs font-medium hover:text-primary transition-colors"
              onClick={() => setShowAnalogs((s) => !s)}
            >
              <span className="flex items-center gap-1">
                <History className="size-3.5" />
                {pkg.analog_events.length} historical analogues
                {pkg.analog_events.filter((a) => a.closure).length > 0 && (
                  <span className="text-destructive ml-1">
                    · {pkg.analog_events.filter((a) => a.closure).length} led to closure
                  </span>
                )}
              </span>
              {showAnalogs ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </button>
            {showAnalogs && (
              <div className="space-y-1.5 animate-in fade-in-0 slide-in-from-top-1 duration-150">
                {pkg.analog_events.map((a) => (
                  <div key={a.event_id} className="flex items-center justify-between text-xs rounded-md bg-muted/60 px-3 py-1.5">
                    <span className="text-muted-foreground">{a.corridor ?? "Non-corridor"} · {a.start_datetime ? new Date(a.start_datetime).toLocaleDateString("en-IN") : "—"}</span>
                    <div className="flex items-center gap-2">
                      {a.closure
                        ? <Badge variant="outline" className="text-[10px] bg-destructive/10 text-destructive border-destructive/30">Closed</Badge>
                        : <Badge variant="outline" className="text-[10px] bg-live/10 text-live border-live/30">No closure</Badge>}
                      {a.ict_h != null && <span className="text-muted-foreground">{a.ict_h.toFixed(1)}h</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Checklist + Compliance */}
        <Separator />
        <button
          className="flex w-full items-center justify-between text-xs font-medium hover:text-primary transition-colors"
          onClick={() => setExpanded((e) => !e)}
        >
          <span>Checklist ({pkg.checklist.length}) {pkg.compliance_items.length > 0 && `· ${pkg.compliance_items.length} compliance`}</span>
          {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </button>
        {expanded && (
          <div className="space-y-3 animate-in fade-in-0 slide-in-from-top-1 duration-150">
            <ul className="space-y-1.5">
              {pkg.checklist.map((item) => (
                <li key={item.id} className="flex items-start gap-2">
                  <Badge variant={item.required ? "default" : "outline"} className="text-[10px] mt-0.5 shrink-0">{item.category}</Badge>
                  <span className="text-xs text-muted-foreground leading-snug">{item.description}</span>
                </li>
              ))}
            </ul>
            {pkg.compliance_items.length > 0 && (
              <>
                <Separator />
                <div className="space-y-1">
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Compliance</p>
                  {pkg.compliance_items.map((item, i) => (
                    <p key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                      <span className="text-primary mt-0.5">·</span>{item}
                    </p>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* Diversion refs — show top 1 on card */}
        {pkg.diversion_refs && pkg.diversion_refs.length > 0 && (
          <>
            <Separator />
            <div className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <Route className="size-3.5 shrink-0 mt-0.5 text-primary/60" />
              <span><span className="font-medium text-foreground">Diversion:</span> {pkg.diversion_refs[0].route_summary}</span>
            </div>
          </>
        )}

        {/* Edit / view button */}
        <div className="pt-1">
          <Button variant="outline" size="sm" className="w-full text-xs h-7" onClick={() => onEdit(pkg)}>
            {canEdit ? "Edit / View full prediction" : "View prediction"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Impact Prediction Panel (shown inside dialog after generation)
// ---------------------------------------------------------------------------

function ImpactPredictionPanel({ pkg, relatedClusters }: { pkg: PlannedEventPackage; relatedClusters: HotspotCluster[] }) {
  const impact = pkg.impact_overlay;

  return (
    <div className="space-y-4 animate-in fade-in-0 slide-in-from-bottom-2 duration-300">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-primary" />
        <p className="text-sm font-semibold">Impact Prediction</p>
        <Badge variant="outline" className={cn("text-[10px] ml-auto", SEVERITY_BADGE[impact.severity_band] ?? "bg-muted text-muted-foreground")}>
          {impact.severity_band} severity
        </Badge>
        {impact.source === "rule_fallback" && (
          <Badge variant="outline" className="text-[10px] bg-muted text-muted-foreground">Rule-based</Badge>
        )}
      </div>

      {/* Core metrics */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-md border bg-muted/40 px-3 py-2.5 text-center">
          <p className="text-[10px] text-muted-foreground mb-1">P(closure)</p>
          <p className={cn("text-lg font-bold tabular-nums", impact.p_closure > 0.7 ? "text-destructive" : impact.p_closure > 0.4 ? "text-warn" : "text-live")}>
            {(impact.p_closure * 100).toFixed(0)}%
          </p>
        </div>
        <div className="rounded-md border bg-muted/40 px-3 py-2.5 text-center">
          <p className="text-[10px] text-muted-foreground mb-1">ICT median</p>
          <p className="text-lg font-bold tabular-nums">{impact.ict_p50_h.toFixed(1)}h</p>
          <p className="text-[10px] text-muted-foreground">p20: {impact.ict_p20_h.toFixed(1)}h · p80: {impact.ict_p80_h.toFixed(1)}h</p>
        </div>
        <div className="rounded-md border bg-muted/40 px-3 py-2.5 text-center">
          <p className="text-[10px] text-muted-foreground mb-1">Staffing</p>
          <p className="text-lg font-bold tabular-nums">{pkg.staffing_min}–{pkg.staffing_max}</p>
          <p className="text-[10px] text-muted-foreground">{pkg.barricade_count} barricades</p>
        </div>
      </div>

      {pkg.barricade_staging_required && (
        <div className="flex items-center gap-2 text-xs text-warn bg-warn/8 border border-warn/20 rounded-md px-3 py-2">
          <AlertTriangle className="size-3.5 shrink-0" />
          Barricade staging required — deploy {pkg.deployment_lead_time_hours}h before start
        </div>
      )}

      {/* Historical analogues */}
      {pkg.analog_events && pkg.analog_events.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
            <History className="size-3.5" />
            Historical analogues ({pkg.analog_events.length} similar past events)
          </p>
          <div className="space-y-1.5">
            {pkg.analog_events.map((a: AnalogEvent) => (
              <div key={a.event_id} className="flex items-center justify-between rounded-md bg-muted/60 px-3 py-2 text-xs">
                <div>
                  <span className="font-medium">{a.corridor ?? "Non-corridor"}</span>
                  {a.start_datetime && <span className="text-muted-foreground ml-1.5">· {new Date(a.start_datetime).toLocaleDateString("en-IN")}</span>}
                </div>
                <div className="flex items-center gap-2">
                  {a.closure
                    ? <Badge variant="outline" className="text-[10px] bg-destructive/10 text-destructive border-destructive/30">Led to closure</Badge>
                    : <Badge variant="outline" className="text-[10px] bg-live/10 text-live border-live/30">No closure</Badge>}
                  {a.ict_h != null && <span className="text-muted-foreground">{a.ict_h.toFixed(1)}h clearance</span>}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-muted-foreground">
            Closure rate: {pkg.analog_events.length > 0
              ? `${Math.round((pkg.analog_events.filter((a: AnalogEvent) => a.closure).length / pkg.analog_events.length) * 100)}%`
              : "—"} from analogues
          </p>
        </div>
      )}

      {/* Related hotspot areas */}
      {relatedClusters.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
            <MapPin className="size-3.5" />
            Historically affected hotspot areas
          </p>
          <div className="space-y-1.5">
            {relatedClusters.slice(0, 3).map((c) => (
              <div key={c.cluster_id} className="flex items-center justify-between rounded-md bg-muted/60 px-3 py-2 text-xs">
                <div>
                  <span className="font-medium">{c.label ?? c.cluster_id}</span>
                  <span className="text-muted-foreground ml-1.5">· {c.corridors.join(", ")}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">density {c.density.toFixed(2)}</span>
                  <Badge variant="outline" className="text-[10px]">
                    persistence {(c.persistence_score * 100).toFixed(0)}%
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Diversion refs */}
      {pkg.diversion_refs && pkg.diversion_refs.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
            <TrendingUp className="size-3.5" />
            Recommended diversions
          </p>
          <div className="space-y-1.5">
            {pkg.diversion_refs.map((d) => (
              <div key={d.junction_id} className="rounded-md bg-muted/60 px-3 py-2 text-xs">
                <p className="font-medium">{d.description}</p>
                <p className="text-muted-foreground">{d.route_summary}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add / Edit Dialog
// ---------------------------------------------------------------------------

interface EventFormState {
  cause: string;
  corridor: string;
  startDate: string;
  startTime: string;
  endDate: string;
  endTime: string;
  description: string;
  requiresClosure: boolean;
}

const EMPTY_FORM: EventFormState = {
  cause: "",
  corridor: "",
  startDate: "",
  startTime: "09:00",
  endDate: "",
  endTime: "18:00",
  description: "",
  requiresClosure: false,
};

function toISOWithIST(date: string, time: string): string | null {
  if (!date) return null;
  const t = time || "00:00";
  return `${date}T${t}:00+05:30`;
}

function pkgToForm(pkg: PlannedEventPackage): EventFormState {
  // We can't recover exact datetime from the package (only hours_until_start)
  // So we reconstruct approximate start from now + hours_until_start
  const startMs = Date.now() + pkg.hours_until_start * 3600 * 1000;
  const startDate = new Date(startMs);
  const pad = (n: number) => String(n).padStart(2, "0");
  const dateStr = `${startDate.getFullYear()}-${pad(startDate.getMonth() + 1)}-${pad(startDate.getDate())}`;
  const timeStr = `${pad(startDate.getHours())}:${pad(startDate.getMinutes())}`;
  const dur = pkg.estimated_duration_h ?? 8;
  const endMs = startMs + dur * 3600 * 1000;
  const endDate = new Date(endMs);
  const endDateStr = `${endDate.getFullYear()}-${pad(endDate.getMonth() + 1)}-${pad(endDate.getDate())}`;
  const endTimeStr = `${pad(endDate.getHours())}:${pad(endDate.getMinutes())}`;

  return {
    cause: pkg.cause,
    corridor: pkg.corridor ?? "",
    startDate: dateStr,
    startTime: timeStr,
    endDate: endDateStr,
    endTime: endTimeStr,
    description: "",
    requiresClosure: pkg.impact_overlay.p_closure > 0.5,
  };
}

function AddEditDialog({
  open,
  editPkg,
  centroids,
  onClose,
  onSaved,
}: {
  open: boolean;
  editPkg: PlannedEventPackage | null;
  centroids: CorridorCentroid[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<EventFormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [predicting, setPredicting] = useState(false);
  const [prediction, setPrediction] = useState<PlannedEventPackage | null>(null);
  const [relatedClusters, setRelatedClusters] = useState<HotspotCluster[]>([]);
  const [error, setError] = useState<string | null>(null);
  const editEventIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (open) {
      setPrediction(null);
      setRelatedClusters([]);
      setError(null);
      editEventIdRef.current = editPkg?.event_id ?? null;
      setForm(editPkg ? pkgToForm(editPkg) : EMPTY_FORM);
    }
  }, [open, editPkg]);

  const set = (field: keyof EventFormState, value: string | boolean) =>
    setForm((f) => ({ ...f, [field]: value }));

  const runPrediction = async () => {
    if (!form.cause || !form.startDate) {
      setError("Cause and start date are required.");
      return;
    }
    setError(null);
    setSaving(true);
    setPrediction(null);
    try {
      const [lat, lng] = resolveCorridorCoords(form.corridor || null, centroids);
      const payload: import("@/lib/types").PlannedIngestPayload = {
        ...(editEventIdRef.current ? { event_id: editEventIdRef.current } : {}),
        event_cause: form.cause,
        corridor: form.corridor || null,
        start_datetime: toISOWithIST(form.startDate, form.startTime)!,
        end_datetime: form.endDate ? toISOWithIST(form.endDate, form.endTime) : null,
        latitude: lat,
        longitude: lng,
        description: form.description || null,
        requires_road_closure: form.requiresClosure,
      };

      const ack = await api.ingestPlanned(payload);
      editEventIdRef.current = ack.event_id;

      // Generate prediction package
      setPredicting(true);
      setSaving(false);
      const pkg = await api.generatePackage(ack.event_id, true);
      setPrediction(pkg);

      // Fetch hotspot clusters to find related areas
      const observed = await api.hotspotsObserved().catch(() => null);
      if (observed && form.corridor) {
        const corr = form.corridor.toLowerCase();
        const related = observed.clusters.filter((c) =>
          c.corridors.some((cr) => cr.toLowerCase().includes(corr) || corr.includes(cr.toLowerCase()))
        );
        setRelatedClusters(related);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate prediction. Please try again.");
    } finally {
      setSaving(false);
      setPredicting(false);
    }
  };

  const handleSave = async () => {
    if (prediction) {
      // Already ingested during prediction — just close and refresh
      onSaved();
      onClose();
      return;
    }
    // No prediction yet — ingest directly
    if (!form.cause || !form.startDate) {
      setError("Cause and start date are required.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const [lat, lng] = resolveCorridorCoords(form.corridor || null, centroids);
      await api.ingestPlanned({
        ...(editEventIdRef.current ? { event_id: editEventIdRef.current } : {}),
        event_cause: form.cause,
        corridor: form.corridor || null,
        start_datetime: toISOWithIST(form.startDate, form.startTime)!,
        end_datetime: form.endDate ? toISOWithIST(form.endDate, form.endTime) : null,
        latitude: lat,
        longitude: lng,
        description: form.description || null,
        requires_road_closure: form.requiresClosure,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save event.");
    } finally {
      setSaving(false);
    }
  };

  const isLoading = saving || predicting;

  const corridorQuery = form.corridor.trim();
  const corridorMatched =
    corridorQuery.length > 0 &&
    centroids.some(
      (c) =>
        c.name.toLowerCase() === corridorQuery.toLowerCase() ||
        c.name.toLowerCase().includes(corridorQuery.toLowerCase()) ||
        corridorQuery.toLowerCase().includes(c.name.toLowerCase()),
    );
  const [hintLat, hintLng] = resolveCorridorCoords(corridorQuery || null, centroids);
  const corridorCoordsHint = `${hintLat.toFixed(4)}, ${hintLng.toFixed(4)}`;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editPkg ? "Edit Planned Event" : "Add Planned Event"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Form */}
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              {/* Cause */}
              <div className="space-y-1.5">
                <Label className="text-xs">Cause <span className="text-destructive">*</span></Label>
                <Select value={form.cause} onValueChange={(v) => v && set("cause", v)}>
                  <SelectTrigger className="h-8 text-sm">
                    <SelectValue placeholder="Select cause…" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(CAUSE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Corridor */}
              <div className="space-y-1.5">
                <Label className="text-xs">Corridor</Label>
                <Input
                  className="h-8 text-sm"
                  placeholder="e.g. Mysore Road"
                  list="corridor-centroids"
                  value={form.corridor}
                  onChange={(e) => set("corridor", e.target.value)}
                />
                <datalist id="corridor-centroids">
                  {centroids.map((c) => (
                    <option key={c.name} value={c.name} />
                  ))}
                </datalist>
                {corridorQuery.length > 0 && (
                  <p className="text-[10px] text-muted-foreground">
                    {corridorMatched
                      ? `Using real centroid ${corridorCoordsHint}`
                      : "No matching centroid — defaults to city centre"}
                  </p>
                )}
              </div>
            </div>

            {/* Start */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Start date <span className="text-destructive">*</span></Label>
                <Input type="date" className="h-8 text-sm" value={form.startDate} onChange={(e) => set("startDate", e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Start time (IST)</Label>
                <Input type="time" className="h-8 text-sm" value={form.startTime} onChange={(e) => set("startTime", e.target.value)} />
              </div>
            </div>

            {/* End */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs">End date (optional)</Label>
                <Input type="date" className="h-8 text-sm" value={form.endDate} onChange={(e) => set("endDate", e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">End time (IST)</Label>
                <Input type="time" className="h-8 text-sm" value={form.endTime} onChange={(e) => set("endTime", e.target.value)} />
              </div>
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label className="text-xs">Notes (optional)</Label>
              <Textarea
                className="text-sm resize-none"
                rows={2}
                placeholder="Additional context for operators…"
                value={form.description}
                onChange={(e) => set("description", e.target.value)}
              />
            </div>

            {/* Road closure */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                className="size-4 rounded"
                checked={form.requiresClosure}
                onChange={(e) => set("requiresClosure", e.target.checked)}
              />
              <span className="text-sm">Requires road closure</span>
            </label>
          </div>

          {error && (
            <p className="text-xs text-destructive flex items-center gap-1.5">
              <AlertTriangle className="size-3.5 shrink-0" />
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 gap-1.5"
              disabled={isLoading || !form.cause || !form.startDate}
              onClick={runPrediction}
            >
              {predicting ? (
                <><RefreshCw className="size-3.5 animate-spin" />Generating prediction…</>
              ) : (
                <><Sparkles className="size-3.5" />Preview impact</>
              )}
            </Button>
            <Button
              size="sm"
              className="flex-1"
              disabled={isLoading || !form.cause || !form.startDate}
              onClick={handleSave}
            >
              {saving ? (
                <><RefreshCw className="size-3.5 animate-spin mr-1.5" />Saving…</>
              ) : prediction ? (
                "Save event"
              ) : (
                "Add event"
              )}
            </Button>
          </div>

          {/* Prediction panel */}
          {predicting && (
            <div className="space-y-3">
              <Skeleton className="h-4 w-48" />
              <div className="grid grid-cols-3 gap-2">
                <Skeleton className="h-16 rounded-md" />
                <Skeleton className="h-16 rounded-md" />
                <Skeleton className="h-16 rounded-md" />
              </div>
              <Skeleton className="h-24 rounded-md" />
            </div>
          )}
          {!predicting && prediction && (
            <>
              <Separator />
              <ImpactPredictionPanel pkg={prediction} relatedClusters={relatedClusters} />
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const HOUR_WINDOWS = [24, 48, 72] as const;
type HourWindow = (typeof HOUR_WINDOWS)[number];

export default function PlannedPage() {
  const { user } = useAuth();
  const canEdit = user ? can.addPlannedEvent(user.role) : false;
  const [packages, setPackages] = useState<PlannedEventPackage[]>([]);
  const [centroids, setCentroids] = useState<CorridorCentroid[]>([]);
  const [loading, setLoading] = useState(true);
  const [hourWindow, setHourWindow] = useState<HourWindow>(72);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editPkg, setEditPkg] = useState<PlannedEventPackage | null>(null);
  const [filterCause, setFilterCause] = useState<string>("all");
  const [filterCorridor, setFilterCorridor] = useState<string>("");

  const load = useCallback(async (hours: HourWindow) => {
    setLoading(true);
    try {
      const data = await api.plannedUpcoming(hours);
      setPackages(data);
      setRefreshedAt(new Date());
    } catch {
      setPackages([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(hourWindow); }, [load, hourWindow]);

  // Real corridor centroids (GET /api/v1/corridors) — drives ingest coordinates
  // for planned events, replacing the old hardcoded lookup.
  useEffect(() => {
    api.corridors()
      .then((res) => setCentroids(res.corridors))
      .catch(() => setCentroids([]));
  }, []);

  const filtered = packages.filter((p) => {
    if (filterCause !== "all" && p.cause !== filterCause) return false;
    if (filterCorridor.trim()) {
      const q = filterCorridor.trim().toLowerCase();
      if (!(p.corridor ?? "").toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    const ord: Record<UrgencyLevel, number> = { critical: 0, high: 1, medium: 2, normal: 3 };
    const diff = ord[urgencyLevel(a)] - ord[urgencyLevel(b)];
    return diff !== 0 ? diff : a.hours_until_start - b.hours_until_start;
  });

  const hasFilters = filterCause !== "all" || filterCorridor.trim() !== "";

  const criticalCount = sorted.filter((p) => urgencyLevel(p) === "critical").length;
  const highCount = sorted.filter((p) => urgencyLevel(p) === "high").length;
  const needsStagingCount = sorted.filter((p) => p.barricade_staging_required).length;
  const lowConfidenceCount = sorted.filter((p) => p.low_confidence_template).length;

  return (
    <div className="flex flex-col h-full">
      <AppHeader title="Planned Events">
        <div className="flex items-center gap-2">
          {/* Window selector */}
          <div className="flex rounded-md border overflow-hidden text-xs">
            {HOUR_WINDOWS.map((w) => (
              <button
                key={w}
                className={cn(
                  "px-2.5 py-1 transition-colors",
                  hourWindow === w
                    ? "bg-primary text-primary-foreground font-medium"
                    : "bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted"
                )}
                onClick={() => setHourWindow(w)}
              >
                {w}h
              </button>
            ))}
          </div>
          {refreshedAt && (
            <span className="text-xs text-muted-foreground hidden sm:inline">{refreshedAt.toLocaleTimeString()}</span>
          )}
          <Button variant="ghost" size="icon" className="size-7" onClick={() => load(hourWindow)} disabled={loading} aria-label="Refresh">
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </Button>
          {canEdit && (
            <Button size="sm" className="gap-1.5" onClick={() => { setEditPkg(null); setDialogOpen(true); }}>
              <Plus className="size-3.5" />
              Add event
            </Button>
          )}
        </div>
      </AppHeader>

      <div className="flex-1 overflow-y-auto">
        <div id="tour-planned-header" className="p-6 max-w-5xl mx-auto space-y-5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300">

          {/* KPI row */}
          {!loading && packages.length > 0 && (
            <div id="tour-planned-kpi" className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard title="Deploy Now" value={criticalCount} icon={ShieldAlert} description="Window closing — act immediately" valueClassName={criticalCount > 0 ? "text-destructive" : "text-live"} />
              <StatCard title="Starting < 6h" value={highCount} icon={Clock} description="High urgency events" valueClassName={highCount > 0 ? "text-destructive" : "text-muted-foreground"} />
              <StatCard title="Need Staging" value={needsStagingCount} icon={Wrench} description="Barricade staging required" valueClassName={needsStagingCount > 0 ? "text-warn" : "text-muted-foreground"} />
              <StatCard title="Low Confidence" value={lowConfidenceCount} icon={AlertTriangle} description="Template match uncertain" valueClassName={lowConfidenceCount > 0 ? "text-warn" : "text-muted-foreground"} />
            </div>
          )}

          {/* Filter bar */}
          {!loading && packages.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Filter className="size-3.5" />
                <span className="font-medium">Filter</span>
                <InfoPopover
                  title="Filter Events"
                  description="Narrow by corridor name (e.g. 'MG Road') or event type. The KPI cards above always reflect the filtered list."
                />
              </div>
              <Input
                className="h-7 text-xs w-44"
                placeholder="Corridor…"
                value={filterCorridor}
                onChange={(e) => setFilterCorridor(e.target.value)}
              />
              <div className="flex items-center rounded-md border overflow-hidden text-xs">
                <button
                  className={cn("px-2.5 py-1 transition-colors", filterCause === "all" ? "bg-primary text-primary-foreground font-medium" : "bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted")}
                  onClick={() => setFilterCause("all")}
                >All</button>
                {Object.entries(CAUSE_LABELS).map(([val, label]) => {
                  const Icon = CAUSE_ICONS[val];
                  return (
                    <button
                      key={val}
                      className={cn("flex items-center gap-1 px-2.5 py-1 border-l transition-colors", filterCause === val ? "bg-primary text-primary-foreground font-medium" : "bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted")}
                      onClick={() => setFilterCause(filterCause === val ? "all" : val)}
                    >
                      <Icon className="size-3" />
                      {label}
                    </button>
                  );
                })}
              </div>
              {hasFilters && (
                <button
                  className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
                  onClick={() => { setFilterCause("all"); setFilterCorridor(""); }}
                >
                  Clear
                </button>
              )}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="grid gap-4 md:grid-cols-2">
              {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-52 w-full rounded-xl" />)}
            </div>
          )}

          {/* Empty — no events at all */}
          {!loading && packages.length === 0 && (
            <EmptyState
              icon={CalendarX}
              title="No planned events"
              description={`No closures or planned events in the next ${hourWindow} hours. Use 'Add event' to schedule one.`}
            />
          )}

          {/* Empty — filtered to zero */}
          {!loading && packages.length > 0 && sorted.length === 0 && (
            <EmptyState
              icon={Filter}
              title="No events match filters"
              description="Try clearing the corridor search or cause filter."
            />
          )}

          {/* Event grid */}
          {!loading && packages.length > 0 && sorted.length > 0 && (
            <>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <CalendarClock className="size-4 shrink-0" />
                <span>
                  {hasFilters
                    ? <><strong className="text-foreground">{sorted.length}</strong> of {packages.length} events</>
                    : <><strong className="text-foreground">{packages.length}</strong> event{packages.length > 1 ? "s" : ""}</>}{" "}
                  in the next {hourWindow}h
                </span>
                {criticalCount > 0 && (
                  <>
                    <span className="text-border">·</span>
                    <span className="text-destructive font-medium flex items-center gap-1">
                      <ShieldAlert className="size-3.5" />
                      {criticalCount} deployment window{criticalCount > 1 ? "s" : ""} closing
                    </span>
                  </>
                )}
              </div>
              <div id="tour-planned-events" className="grid gap-4 md:grid-cols-2">
                {sorted.map((pkg) => (
                  <EventCard
                    key={pkg.event_id}
                    pkg={pkg}
                    canEdit={canEdit}
                    onEdit={(p) => { setEditPkg(p); setDialogOpen(true); }}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Add / Edit dialog */}
      {canEdit && (
        <AddEditDialog
          open={dialogOpen}
          editPkg={editPkg}
          centroids={centroids}
          onClose={() => setDialogOpen(false)}
          onSaved={() => load(hourWindow)}
        />
      )}
    </div>
  );
}
