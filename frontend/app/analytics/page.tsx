"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { StatCard } from "@/components/stat-card";
import { InfoPopover } from "@/components/info-popover";
import { api } from "@/lib/api";
import type {
  AnomaliesResponse,
  AnomalyAlert,
  CellHistorySummary,
  DensityHotspotsResponse,
  PredictedHotspotsResponse,
  PredictedZoneForecast,
} from "@/lib/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Hourly area chart — unchanged from previous version, it's genuinely useful
// ---------------------------------------------------------------------------
function HourlyAreaChart({ counts }: { counts: number[] }) {
  const W = 440, H = 120;
  const PAD = { l: 28, r: 10, t: 10, b: 24 };
  const cW = W - PAD.l - PAD.r;
  const cH = H - PAD.t - PAD.b;
  const max = Math.max(...counts, 1);

  const px = (i: number) => PAD.l + (i / (counts.length - 1)) * cW;
  const py = (v: number) => PAD.t + cH - (v / max) * cH;
  const pts = counts.map((v, i) => [px(i), py(v)] as [number, number]);
  const line = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${(PAD.t + cH).toFixed(1)} L${pts[0][0].toFixed(1)},${(PAD.t + cH).toFixed(1)} Z`;
  const peakSet = new Set(
    [...counts].map((v, i) => ({ v, i })).sort((a, b) => b.v - a.v).slice(0, 3).map(({ i }) => i)
  );
  const yTicks = [0, Math.round(max / 2), max];
  const xTicks = [0, 6, 12, 18, 23];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label="Hourly event pattern">
      <defs>
        <linearGradient id="hrly-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {yTicks.map((v) => (
        <g key={v}>
          <line x1={PAD.l} y1={py(v)} x2={W - PAD.r} y2={py(v)} stroke="var(--border)" strokeWidth="0.6" />
          <text x={PAD.l - 4} y={py(v) + 3.5} fontSize="9" fill="var(--muted-foreground)" textAnchor="end">{v}</text>
        </g>
      ))}
      <path d={area} fill="url(#hrly-grad)" />
      <path d={line} fill="none" stroke="var(--primary)" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
      {counts.map((v, i) => peakSet.has(i) ? (
        <circle key={i} cx={px(i)} cy={py(v)} r="3" fill="var(--primary)" stroke="var(--card)" strokeWidth="1.5" />
      ) : null)}
      <line x1={PAD.l} y1={PAD.t + cH} x2={W - PAD.r} y2={PAD.t + cH} stroke="var(--border)" strokeWidth="1" />
      {xTicks.map((h) => (
        <g key={h}>
          <line x1={px(h)} y1={PAD.t + cH} x2={px(h)} y2={PAD.t + cH + 3} stroke="var(--border)" strokeWidth="1" />
          <text x={px(h)} y={H - 4} fontSize="9" fill="var(--muted-foreground)" textAnchor="middle">{h}h</text>
        </g>
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
type CorridorStatus = "at_risk" | "elevated" | "normal" | "below";

function corridorStatus(lift: number): CorridorStatus {
  if (lift > 15) return "at_risk";
  if (lift > 5)  return "elevated";
  if (lift < -5) return "below";
  return "normal";
}

function StatusBadge({ status, anomaly = false }: { status: CorridorStatus; anomaly?: boolean }) {
  const cfg: Record<CorridorStatus, { label: string; className: string }> = {
    at_risk:  { label: "At Risk",  className: "bg-destructive/10 text-destructive border-destructive/30" },
    elevated: { label: "Elevated", className: "bg-warn/10 text-warn border-warn/30" },
    normal:   { label: "Normal",   className: "bg-muted text-muted-foreground border-border" },
    below:    { label: "Below Baseline", className: "bg-live/10 text-live border-live/30" },
  };
  const { label, className } = cfg[status];
  return (
    <Badge variant="outline" className={cn("text-[10px] gap-1", className)}>
      {anomaly && <AlertTriangle className="size-2.5" />}
      {label}
    </Badge>
  );
}

function LiftLabel({ lift }: { lift: number }) {
  const color =
    lift > 15 ? "text-destructive" :
    lift > 5  ? "text-warn" :
    lift < -5 ? "text-live" :
    "text-muted-foreground";
  return (
    <span className={cn("font-mono tabular-nums text-xs inline-flex items-center gap-0.5", color)}>
      {lift > 0 ? <TrendingUp className="size-3" /> : lift < 0 ? <TrendingDown className="size-3" /> : null}
      {lift > 0 ? "+" : ""}{lift.toFixed(1)}%
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [density, setDensity] = useState<DensityHotspotsResponse | null>(null);
  const [predicted, setPredicted] = useState<PredictedHotspotsResponse | null>(null);
  const [anomalies, setAnomalies] = useState<AnomaliesResponse | null>(null);
  const [cellHistory, setCellHistory] = useState<CellHistorySummary | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dens, pred, anom] = await Promise.all([
        api.hotspotsDensity(1),
        api.hotspotsPredicted(4),
        api.hotspotsAnomalies(24),
      ]);
      setDensity(dens);
      setPredicted(pred);
      setAnomalies(anom);
      setRefreshedAt(new Date());
      const topCell = [...dens.cells].sort((a, b) => b.count - a.count)[0];
      if (topCell) {
        const hist = await api.hotspotsCell(topCell.h3_res7).catch(() => null);
        setCellHistory(hist);
      }
    } catch { /* silently degrade */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Derived data
  const anomalySet = new Set((anomalies?.alerts ?? []).map((a) => a.corridor));

  const corridorRows: (PredictedZoneForecast & { status: CorridorStatus; hasAnomaly: boolean })[] =
    [...(predicted?.forecasts ?? [])]
      .map((f) => ({
        ...f,
        status: corridorStatus(f.lift_pct),
        hasAnomaly: anomalySet.has(f.corridor),
      }))
      .sort((a, b) => {
        const ord: Record<CorridorStatus, number> = { at_risk: 0, elevated: 1, normal: 2, below: 3 };
        const diff = ord[a.status] - ord[b.status];
        if (diff !== 0) return diff;
        return b.lift_pct - a.lift_pct;
      });

  const atRiskCount = corridorRows.filter((r) => r.status === "at_risk" || r.hasAnomaly).length;
  const elevatedCount = corridorRows.filter((r) => r.status === "elevated").length;
  const anomalyCount = anomalies?.alerts.length ?? 0;
  const totalEvents = density?.cells.reduce((s, c) => s + c.count, 0) ?? 0;
  const topCauses = (cellHistory?.top_causes ?? []).slice(0, 5) as { cause: string; count: number }[];

  // Banner variant
  const bannerVariant: "danger" | "warn" | "ok" =
    atRiskCount > 0 ? "danger" :
    elevatedCount > 0 ? "warn" : "ok";

  const bannerText =
    bannerVariant === "danger"
      ? `${atRiskCount} corridor${atRiskCount > 1 ? "s" : ""} need${atRiskCount === 1 ? "s" : ""} attention — congestion above 15% threshold${anomalyCount > 0 ? `, ${anomalyCount} CUSUM anomal${anomalyCount > 1 ? "ies" : "y"} detected` : ""}`
      : bannerVariant === "warn"
      ? `${elevatedCount} corridor${elevatedCount > 1 ? "s" : ""} elevated — above 5% baseline threshold in the next 4 h`
      : "All corridors within normal operating bounds — no action required";

  return (
    <div className="flex flex-col h-full">
      <AppHeader title="Analytics">
        <div className="flex items-center gap-2">
          {refreshedAt && (
            <span className="text-xs text-muted-foreground hidden sm:inline">
              Updated {refreshedAt.toLocaleTimeString()}
            </span>
          )}
          <Button variant="ghost" size="icon" className="size-7" onClick={load} disabled={loading} aria-label="Refresh analytics">
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </Button>
        </div>
      </AppHeader>

      <div className="flex-1 overflow-y-auto">
        <div id="tour-analytics-header" className="p-6 max-w-6xl mx-auto space-y-5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300">

          {/* ── Situation Banner ─────────────────────────────────── */}
          {!loading && (
            <div className={cn(
              "flex items-center gap-3 rounded-lg border px-4 py-3 text-sm font-medium",
              bannerVariant === "danger" && "border-destructive/40 bg-destructive/8 text-destructive",
              bannerVariant === "warn"   && "border-warn/40 bg-warn/8 text-warn",
              bannerVariant === "ok"     && "border-live/40 bg-live/8 text-live",
            )}>
              {bannerVariant === "ok"
                ? <CheckCircle2 className="size-4 shrink-0" />
                : <AlertTriangle className="size-4 shrink-0" />}
              {bannerText}
            </div>
          )}

          {/* ── KPI row ──────────────────────────────────────────── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)
            ) : (
              <>
                <StatCard
                  title="At Risk / Elevated"
                  value={`${atRiskCount} / ${elevatedCount}`}
                  icon={AlertTriangle}
                  description="Corridors above threshold"
                  valueClassName={atRiskCount > 0 ? "text-destructive" : elevatedCount > 0 ? "text-warn" : "text-live"}
                />
                <StatCard
                  title="CUSUM Anomalies"
                  value={anomalyCount}
                  icon={Zap}
                  description="Detected in last 24 h"
                  valueClassName={anomalyCount > 0 ? "text-destructive" : "text-live"}
                />
                <StatCard
                  title="Corridors Tracked"
                  value={predicted?.forecasts.length ?? 0}
                  icon={BarChart3}
                  description="In Poisson forecast model"
                />
                <StatCard
                  title="Historical Events"
                  value={totalEvents.toLocaleString()}
                  icon={Activity}
                  description="Across all H3 cells"
                />
              </>
            )}
          </div>

          {/* ── HERO: Corridor Watch ──────────────────────────────── */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-1.5">
                    <CardTitle className="text-sm">Corridor Watch — Next 4 Hours</CardTitle>
                    <InfoPopover
                      title="Corridor Watch"
                      description="Poisson model forecast for the next 4 hours across major corridors. 'At Risk' means event volume is predicted >15% above the historical baseline — expect congestion."
                    />
                  </div>
                  <CardDescription className="text-xs mt-0.5">
                    Ranked by urgency. <span className="text-destructive font-medium">At Risk</span> = &gt;15% above baseline.{" "}
                    <span className="text-warn font-medium">Elevated</span> = &gt;5%.{" "}
                    <span className="text-live font-medium">Below Baseline</span> = &lt;−5%.{" "}
                    ⚠ = CUSUM anomaly also detected.
                  </CardDescription>
                </div>
                {!loading && <Badge variant="outline" className="shrink-0 text-xs">{corridorRows.length} corridors</Badge>}
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {loading ? (
                <Skeleton className="h-64 w-full rounded-lg" />
              ) : corridorRows.length === 0 ? (
                <EmptyState icon={BarChart3} title="No forecast data" description="The Poisson model has not produced forecasts yet." className="py-8" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-6">#</TableHead>
                      <TableHead>Corridor</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">vs. Baseline</TableHead>
                      <TableHead className="text-right hidden md:table-cell">Baseline / 4h</TableHead>
                      <TableHead className="text-right hidden md:table-cell">Predicted / 4h</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {corridorRows.map((row, i) => (
                      <TableRow
                        key={row.corridor}
                        className={cn(
                          row.status === "at_risk" && "bg-destructive/4",
                          row.status === "elevated" && "bg-warn/4",
                        )}
                      >
                        <TableCell className="text-xs text-muted-foreground tabular-nums w-6">{i + 1}</TableCell>
                        <TableCell className="font-medium text-sm">{row.corridor}</TableCell>
                        <TableCell><StatusBadge status={row.status} anomaly={row.hasAnomaly} /></TableCell>
                        <TableCell className="text-right"><LiftLabel lift={row.lift_pct} /></TableCell>
                        <TableCell className="text-right font-mono text-xs text-muted-foreground tabular-nums hidden md:table-cell">
                          {row.baseline_count.toFixed(3)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs tabular-nums hidden md:table-cell">
                          {row.expected_count.toFixed(3)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* ── Anomaly detail + Hourly pattern ──────────────────── */}
          <div className="grid lg:grid-cols-2 gap-4">

            {/* Anomaly detail */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <CardTitle className="text-sm">CUSUM Anomaly Detail</CardTitle>
                      <InfoPopover
                        title="CUSUM Anomaly Detection"
                        description="CUSUM (Cumulative Sum) is a statistical test that flags when a corridor's event rate has shifted significantly from its normal pattern — like a sudden spike not explained by known planned events."
                      />
                    </div>
                    <CardDescription className="text-xs mt-0.5">Corridors with statistically unusual event rates (last 24 h)</CardDescription>
                  </div>
                  {anomalyCount > 0 && (
                    <Badge variant="destructive" className="shrink-0 text-xs">{anomalyCount} active</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                {loading ? (
                  <Skeleton className="h-40 w-full rounded-lg" />
                ) : anomalyCount === 0 ? (
                  <EmptyState
                    icon={CheckCircle2}
                    title="No anomalies detected"
                    description="All corridors within normal operating bounds."
                    className="py-8"
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Corridor</TableHead>
                        <TableHead className="text-right">Observed /h</TableHead>
                        <TableHead className="text-right">Baseline /h</TableHead>
                        <TableHead className="text-right">Sigma</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {[...(anomalies?.alerts ?? [])].sort((a: AnomalyAlert, b: AnomalyAlert) => b.sigma - a.sigma).map((alert: AnomalyAlert) => (
                        <TableRow key={alert.alert_id}>
                          <TableCell className="font-medium text-sm">{alert.corridor}</TableCell>
                          <TableCell className="text-right font-mono text-xs text-destructive tabular-nums">{alert.observed_rate_per_hour.toFixed(2)}</TableCell>
                          <TableCell className="text-right font-mono text-xs text-muted-foreground tabular-nums">{alert.baseline_rate_per_hour.toFixed(2)}</TableCell>
                          <TableCell className="text-right">
                            <span className={cn(
                              "font-mono text-xs font-semibold tabular-nums",
                              alert.sigma > 3 ? "text-destructive" : "text-warn"
                            )}>
                              {alert.sigma.toFixed(1)}σ
                            </span>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            {/* Hourly pattern for densest cell */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-1.5">
                  <CardTitle className="text-sm">Hourly Congestion Pattern</CardTitle>
                  <InfoPopover
                    title="Hourly Congestion Pattern"
                    description="Shows how events are distributed by hour of day at the densest active grid cell. Peaks reveal rush-hour patterns and recurring congestion windows for proactive deployment."
                  />
                </div>
                <CardDescription className="text-xs mt-0.5">
                  Events by hour of day (IST) — densest active hotspot cell
                  {cellHistory && (
                    <span className="ml-1 font-mono text-[10px] opacity-60">{cellHistory.h3_res7.slice(0, 10)}…</span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0 space-y-3">
                {loading ? (
                  <Skeleton className="h-40 w-full rounded-lg" />
                ) : cellHistory ? (
                  <>
                    <HourlyAreaChart counts={cellHistory.hourly_counts} />
                    <div className="grid grid-cols-3 gap-2">
                      <div className="rounded-md bg-muted/60 px-2 py-2 text-center">
                        <p className="text-[10px] text-muted-foreground mb-0.5">Total</p>
                        <p className="text-sm font-semibold tabular-nums">{cellHistory.total_events.toLocaleString()}</p>
                      </div>
                      <div className="rounded-md bg-muted/60 px-2 py-2 text-center">
                        <p className="text-[10px] text-muted-foreground mb-0.5">Last 30 d</p>
                        <p className="text-sm font-semibold tabular-nums">{cellHistory.events_30d.toLocaleString()}</p>
                      </div>
                      <div className="rounded-md bg-muted/60 px-2 py-2 text-center">
                        <p className="text-[10px] text-muted-foreground mb-0.5">Persistence</p>
                        <p className="text-sm font-semibold tabular-nums">{(cellHistory.persistence_score * 100).toFixed(0)}%</p>
                      </div>
                    </div>
                    {topCauses.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Top causes at this cell</p>
                        <div className="flex flex-wrap gap-1">
                          {topCauses.map(({ cause, count }) => (
                            <Badge key={cause} variant="secondary" className="text-[10px] gap-1">
                              {cause}<span className="text-muted-foreground font-normal">· {count}</span>
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <EmptyState icon={Activity} title="No cell data" description="Historical index not yet populated." className="py-8" />
                )}
              </CardContent>
            </Card>
          </div>

          {/* ── Planned features ─────────────────────────────────── */}
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Planned Features — Require Live Event Data</p>
            <div className="grid md:grid-cols-3 gap-4">
              <Card className="opacity-70">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="size-4 text-muted-foreground" />
                    <CardTitle className="text-sm">RCI Trends</CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    Road Criticality Index over time per corridor — shows whether conditions are improving or degrading.
                    Needs live events ingested via <code className="font-mono text-[10px]">POST /ingest</code>.
                  </CardDescription>
                </CardHeader>
              </Card>
              <Card className="opacity-70">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Clock className="size-4 text-muted-foreground" />
                    <CardTitle className="text-sm">Corridor Performance</CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    Average ICT (Incident Clearance Time) per corridor vs. SLA targets.
                    Requires completed closures in the database.
                  </CardDescription>
                </CardHeader>
              </Card>
              <Card className="opacity-70">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Users className="size-4 text-muted-foreground" />
                    <CardTitle className="text-sm">Citizen Triage</CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    Incoming citizen reports by status (pending / verified / rejected) and cause breakdown.
                    Needs a <code className="font-mono text-[10px]">GET /citizen/reports</code> list endpoint (not yet built).
                  </CardDescription>
                </CardHeader>
              </Card>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
