"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { can } from "@/lib/auth";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  History,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoPopover } from "@/components/info-popover";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppHeader } from "@/components/app-header";
import { StatCard } from "@/components/stat-card";
import { api } from "@/lib/api";
import type {
  BufferManifestResponse,
  DrillResult,
  EvalResponse,
  GovernanceTierResponse,
  HealthRollup,
  LatestJobResponse,
  PromotionChecklistResponse,
  Tier,
  TierTransition,
} from "@/lib/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const OPERATOR_ID = "CMD-DASHBOARD";

const TIER_CONFIG: Record<Tier, {
  label: string;
  description: string;
  badge: string;
  icon: typeof Shield;
}> = {
  "1": {
    label: "Tier 1 — Full AI",
    description: "MILP primary dispatch + ML scoring + live APIs + dynamic routing. All AI capabilities active.",
    badge: "bg-live/10 text-live border-live/30",
    icon: ShieldCheck,
  },
  "2": {
    label: "Tier 2 — Constrained",
    description: "Simplified fallback dispatch + rule-based scoring. Triggered automatically when the AI impact model is unavailable.",
    badge: "bg-warn/10 text-warn border-warn/30",
    icon: ShieldAlert,
  },
  "3": {
    label: "Tier 3 — Manual SOP",
    description: "Static standard-procedure templates + manual command mode only. Triggered when data ingestion and the feature store are both down.",
    badge: "bg-destructive/10 text-destructive border-destructive/30",
    icon: Shield,
  },
};

// Backend sends internal codes (e.g. "M01_Ingestion") — map to plain names for display.
const MODULE_DISPLAY_NAMES: Record<string, string> = {
  M01_Ingestion: "Data Ingestion",
  M02_Features: "Feature Store",
  M03_Impact: "AI Impact Engine",
};

function moduleDisplayName(code: string): string {
  return MODULE_DISPLAY_NAMES[code] ?? code;
}

const STATUS_CONFIG: Record<string, { dot: string; badgeClass: string; label: string }> = {
  healthy:  { dot: "bg-live",         badgeClass: "bg-live/10 text-live border-live/30",               label: "healthy" },
  degraded: { dot: "bg-warn",         badgeClass: "bg-warn/10 text-warn border-warn/30",               label: "degraded" },
  down:     { dot: "bg-destructive",  badgeClass: "bg-destructive/10 text-destructive border-destructive/30", label: "down" },
};

// ---------------------------------------------------------------------------
// Tier Control Panel — top, always visible
// ---------------------------------------------------------------------------

function TierControlPanel() {
  const { user } = useAuth();
  const canOverride = user ? can.overrideTier(user.role) : false;
  const [tierState, setTierState] = useState<GovernanceTierResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [overriding, setOverriding] = useState(false);
  const [shadowToggling, setShadowToggling] = useState(false);
  const [showOverride, setShowOverride] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [targetTier, setTargetTier] = useState<Tier | null>(null);

  const load = useCallback(() => {
    api.governanceTier()
      .then((t) => { setTierState(t); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 15_000);
    return () => clearInterval(iv);
  }, [load]);

  const handleOverride = async () => {
    if (!targetTier || !overrideReason.trim()) return;
    setOverriding(true);
    try {
      const updated = await api.overrideTier(targetTier, overrideReason.trim(), OPERATOR_ID);
      setTierState(updated);
      setShowOverride(false);
      setOverrideReason("");
      setTargetTier(null);
      toast.success(`Tier overridden to Tier ${updated.tier}`);
    } catch {
      toast.error("Tier override failed");
    } finally {
      setOverriding(false);
    }
  };

  const handleShadowToggle = async () => {
    if (!tierState) return;
    setShadowToggling(true);
    try {
      const updated = await api.setShadowMode(!tierState.shadow_mode, OPERATOR_ID);
      setTierState(updated);
      toast.success(updated.shadow_mode ? "Shadow mode enabled" : "Shadow mode disabled");
    } catch {
      toast.error("Shadow mode toggle failed");
    } finally {
      setShadowToggling(false);
    }
  };

  if (loading) return <Skeleton className="h-32 w-full rounded-xl" />;

  const tier = tierState?.tier ?? "1";
  const cfg = TIER_CONFIG[tier];
  const TierIcon = cfg.icon;

  return (
    <Card className={cn("border-l-4", tier === "1" ? "border-l-live" : tier === "2" ? "border-l-warn" : "border-l-destructive")}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <TierIcon className={cn("size-5 mt-0.5 shrink-0", tier === "1" ? "text-live" : tier === "2" ? "text-warn" : "text-destructive")} />
            <div>
              <CardTitle className="text-sm">{cfg.label}</CardTitle>
              <CardDescription className="text-xs mt-1 max-w-lg">{cfg.description}</CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {tierState?.shadow_mode && (
              <Badge variant="outline" className="text-xs bg-primary/8 text-primary border-primary/20 gap-1">
                <span className="size-1.5 rounded-full bg-primary inline-block" />
                Shadow mode
              </Badge>
            )}
            {tierState?.manual_mode && (
              <Badge variant="outline" className="text-xs bg-warn/10 text-warn border-warn/30">Manual override</Badge>
            )}
            {tierState?.updated_by && (
              <span className="text-[10px] text-muted-foreground hidden sm:inline">by {tierState.updated_by}</span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Tier override buttons — admin only */}
          <div className="flex items-center gap-1 text-xs text-muted-foreground mr-1">Override tier:</div>
          {(["1", "2", "3"] as Tier[]).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={tier === t ? "default" : "outline"}
              className="h-7 text-xs"
              disabled={tier === t || overriding || !canOverride}
              title={!canOverride ? "Admin role required" : undefined}
              onClick={() => { setTargetTier(t); setShowOverride(true); }}
            >
              Tier {t}
            </Button>
          ))}
          <Separator orientation="vertical" className="h-5 mx-1" />
          {/* Shadow mode toggle — admin only */}
          <Button
            size="sm"
            variant="outline"
            className={cn("h-7 text-xs gap-1.5", tierState?.shadow_mode && "border-primary/40 text-primary")}
            disabled={shadowToggling || !canOverride}
            title={!canOverride ? "Admin role required" : undefined}
            onClick={handleShadowToggle}
          >
            {shadowToggling ? <RefreshCw className="size-3 animate-spin" /> : <span className={cn("size-1.5 rounded-full", tierState?.shadow_mode ? "bg-primary" : "bg-muted-foreground")} />}
            {tierState?.shadow_mode ? "Disable shadow mode" : "Enable shadow mode"}
          </Button>
          {!canOverride && (
            <span className="text-[10px] text-muted-foreground italic">Admin role required for tier control</span>
          )}
        </div>

        {/* Override reason input */}
        {showOverride && targetTier && canOverride && (
          <div className="rounded-md border bg-muted/40 p-3 space-y-2 animate-in fade-in-0 slide-in-from-top-1 duration-150">
            <p className="text-xs font-medium">Override to Tier {targetTier} — provide reason for audit log</p>
            <div className="flex gap-2">
              <Input
                className="h-7 text-xs flex-1"
                placeholder="e.g. VIP movement on MG Road, manual control required"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleOverride()}
              />
              <Button size="sm" className="h-7 text-xs" disabled={!overrideReason.trim() || overriding} onClick={handleOverride}>
                {overriding ? <RefreshCw className="size-3 animate-spin" /> : "Confirm"}
              </Button>
              <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => { setShowOverride(false); setTargetTier(null); }}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Auto-transition rules explanation */}
        <div className="text-[10px] text-muted-foreground flex flex-wrap gap-x-4 gap-y-0.5 pt-1">
          <span>Auto: data ingestion + feature store both down → Tier 3</span>
          <span>Auto: AI impact model down → Tier 2</span>
          <span>Auto: healthy ≥5 min → recovery</span>
          <span>Manual override takes precedence until healthy ≥5 min</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Health Panel
// ---------------------------------------------------------------------------

function HealthPanel() {
  const [health, setHealth] = useState<HealthRollup | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [refreshed, setRefreshed] = useState<Date | null>(null);

  const load = useCallback(() => {
    api.governanceHealth().then((h) => { setHealth(h); setRefreshed(new Date()); }).catch(() => {});
  }, []);

  useEffect(() => { load(); const iv = setInterval(load, 30_000); return () => clearInterval(iv); }, [load]);

  if (!health) return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">{[1,2,3].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );

  const healthyCount = health.modules.filter((m) => m.status === "healthy").length;
  const degradedCount = health.modules.filter((m) => m.status === "degraded").length;
  const downCount = health.modules.filter((m) => m.status === "down").length;

  const toggleExpanded = (mod: string) =>
    setExpanded((prev) => { const s = new Set(prev); s.has(mod) ? s.delete(mod) : s.add(mod); return s; });

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        <StatCard title="Modules" value={health.modules.length} icon={ShieldCheck} description="Monitored subsystems" />
        <StatCard title="Healthy" value={healthyCount} icon={CheckCircle2} description="Operating normally" valueClassName="text-live" />
        <StatCard title="Degraded / Down" value={`${degradedCount} / ${downCount}`} icon={XCircle} description="Requiring attention" valueClassName={downCount > 0 ? "text-destructive" : degradedCount > 0 ? "text-warn" : "text-live"} />
      </div>

      {/* AI impact model rule-fallback note */}
      {health.modules.some((m) => m.module.includes("M03") && m.status === "down") && (
        <div className="flex items-start gap-2 text-xs rounded-md border border-warn/30 bg-warn/8 px-3 py-2.5 text-warn">
          <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
          <span>
            <strong>AI Impact Engine</strong> shows "down" because its ML models are not loaded. The system is still functional —
            it's running rule-based fallback scoring (Tier 2 behavior). This is not a critical failure.
          </span>
        </div>
      )}

      <Card>
        <CardHeader id="tour-governance-health" className="flex-row items-center justify-between pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Badge variant="outline" className={cn("gap-1.5 text-xs", STATUS_CONFIG[health.overall_status]?.badgeClass)}>
              <span className={cn("size-1.5 rounded-full", STATUS_CONFIG[health.overall_status]?.dot)} />
              {health.overall_status}
            </Badge>
            Module Health
            <InfoPopover
              title="Module Health"
              description="These are the dashboard's core systems: data ingestion pulls in new incidents, the feature store prepares data for the AI, and the impact engine scores risk with ML models. If ingestion and the feature store both go down, the system drops to Tier 3 (manual mode). If only the impact engine goes down, it drops to Tier 2 (rule-based fallback). Click a row to see detailed metrics."
              side="right"
            />
          </CardTitle>
          <div className="flex items-center gap-2">
            {refreshed && (
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="size-3" />{refreshed.toLocaleTimeString()}
              </span>
            )}
            <Button variant="ghost" size="icon" className="size-7" onClick={load}>
              <RefreshCw className="size-3.5" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-4 pl-4" />
                <TableHead>Module</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-muted-foreground">Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {health.modules.map((m) => {
                const cfg = STATUS_CONFIG[m.status] ?? STATUS_CONFIG.degraded;
                const hasMetrics = Object.keys(m.metrics ?? {}).length > 0;
                const isExpanded = expanded.has(m.module);
                return (
                  <Fragment key={m.module}>
                    <TableRow
                      className={cn(hasMetrics && "cursor-pointer hover:bg-muted/40")}
                      onClick={() => hasMetrics && toggleExpanded(m.module)}
                    >
                      <TableCell className="pl-4 pr-0 w-4">
                        {hasMetrics && (
                          isExpanded
                            ? <ChevronDown className="size-3 text-muted-foreground" />
                            : <ChevronRight className="size-3 text-muted-foreground" />
                        )}
                      </TableCell>
                      <TableCell className="font-medium text-sm">{moduleDisplayName(m.module)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <span className={cn("size-1.5 rounded-full shrink-0", cfg.dot)} />
                          <Badge variant="outline" className={cn("text-xs", cfg.badgeClass)}>{cfg.label}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{m.detail}</TableCell>
                    </TableRow>
                    {isExpanded && hasMetrics && (
                      <TableRow>
                        <TableCell colSpan={4} className="py-2 px-6 bg-muted/30">
                          <div className="flex flex-wrap gap-x-6 gap-y-1">
                            {Object.entries(m.metrics).map(([k, v]) => (
                              <div key={k} className="text-xs">
                                <span className="text-muted-foreground">{k}: </span>
                                <span className="font-mono font-medium">{String(v)}</span>
                              </div>
                            ))}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit Log Panel
// ---------------------------------------------------------------------------

function AuditPanel() {
  const [transitions, setTransitions] = useState<TierTransition[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.governanceTransitions(50)
      .then((r) => setTransitions(r.transitions))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton className="h-64 w-full rounded-xl" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <History className="size-4" />
        <span>Last {transitions.length} tier transitions — all changes logged with operator and reason</span>
      </div>
      <Card>
        <CardContent className="p-0">
          {transitions.length === 0 ? (
            <div className="py-12 text-center">
              <History className="size-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm font-medium">No tier transitions yet</p>
              <p className="text-xs text-muted-foreground mt-1">Transitions appear here when tier overrides or auto-degradations occur.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Change</TableHead>
                  <TableHead>Triggered by</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transitions.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="text-xs text-muted-foreground tabular-nums">
                      {new Date(t.created_at).toLocaleString("en-IN")}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5 text-xs">
                        {t.from_tier && (
                          <Badge variant="outline" className={cn("text-[10px]", TIER_CONFIG[t.from_tier]?.badge)}>T{t.from_tier}</Badge>
                        )}
                        {t.from_tier && <ChevronRight className="size-3 text-muted-foreground" />}
                        <Badge variant="outline" className={cn("text-[10px]", TIER_CONFIG[t.to_tier]?.badge)}>T{t.to_tier}</Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs">
                      {t.operator_id
                        ? <span className="font-medium">{t.operator_id}</span>
                        : <span className="text-muted-foreground italic">auto</span>}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-xs truncate">{t.reason}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drills Panel
// ---------------------------------------------------------------------------

function DrillsPanel() {
  const { user } = useAuth();
  const canRun = user ? can.runDrill(user.role) : false;
  const [last, setLast] = useState<DrillResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => { api.lastCascadeDrill().then(setLast); }, []);

  async function runDrill() {
    setRunning(true);
    try {
      const result = await api.triggerCascadeDrill();
      setLast(result);
      toast[result.passed ? "success" : "error"](result.detail);
    } catch {
      toast.error("Drill failed to run");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Cascade Drill</CardTitle>
          <CardDescription className="text-xs">
            Injects concurrent high-severity closures to force MILP timeout and validate that greedy fallback
            responds within the 1.8s dispatch deadline. Tests: multi-corridor blocked edges, conflicting station load,
            forced MILP timeout. PRD requires this runs nightly.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            onClick={runDrill}
            disabled={running || !canRun}
            title={!canRun ? "Admin role required" : undefined}
            className="gap-2"
          >
            <Zap className={cn("size-4", running && "animate-pulse")} />
            {running ? "Running drill…" : "Trigger cascade drill"}
          </Button>
          {!canRun && (
            <p className="text-xs text-muted-foreground mt-2">Admin role required to run drills.</p>
          )}
        </CardContent>
      </Card>

      {last && (
        <Card className={cn("border-l-4", last.passed ? "border-l-live" : "border-l-destructive")}>
          <CardHeader>
            <CardTitle className="text-sm flex items-center justify-between">
              <span>Last Result — {new Date(last.created_at).toLocaleString("en-IN")}</span>
              <Badge variant={last.passed ? "default" : "destructive"} className="gap-1.5">
                {last.passed ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
                {last.passed ? "PASSED" : "FAILED"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center rounded-md bg-muted/60 px-3 py-2">
                <p className="text-xs text-muted-foreground mb-0.5">Concurrent closures</p>
                <p className="font-bold tabular-nums">{last.concurrent_closures}</p>
              </div>
              <div className="text-center rounded-md bg-muted/60 px-3 py-2">
                <p className="text-xs text-muted-foreground mb-0.5">Fallback rate</p>
                <p className={cn("font-bold tabular-nums", last.fallback_rate < 1 ? "text-warn" : "text-live")}>
                  {(last.fallback_rate * 100).toFixed(0)}%
                </p>
                <p className="text-[10px] text-muted-foreground">should be 100%</p>
              </div>
              <div className="text-center rounded-md bg-muted/60 px-3 py-2">
                <p className="text-xs text-muted-foreground mb-0.5">Max latency</p>
                <p className={cn("font-bold tabular-nums", last.max_latency_ms > last.deadline_ms ? "text-destructive" : "text-live")}>
                  {last.max_latency_ms.toFixed(0)}<span className="text-xs font-normal text-muted-foreground ml-0.5">ms</span>
                </p>
                <p className="text-[10px] text-muted-foreground">deadline {last.deadline_ms}ms</p>
              </div>
            </div>
            {last.detail && (
              <>
                <Separator />
                <p className="text-xs text-muted-foreground">{last.detail}</p>
              </>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="border-dashed">
        <CardContent className="py-4">
          <p className="text-xs text-muted-foreground font-medium mb-2">Auto-transition rules (for reference)</p>
          <div className="space-y-1.5 text-xs text-muted-foreground">
            <div className="flex items-start gap-2"><span className="text-destructive font-medium w-20 shrink-0">→ Tier 3</span><span>Data ingestion AND the feature store both down simultaneously</span></div>
            <div className="flex items-start gap-2"><span className="text-warn font-medium w-20 shrink-0">→ Tier 2</span><span>AI impact model down — simplified dispatch + rule-based scoring takes over</span></div>
            <div className="flex items-start gap-2"><span className="text-live font-medium w-20 shrink-0">→ Tier 1</span><span>All modules healthy for ≥5 consecutive minutes (hysteresis prevents flapping)</span></div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Learning + Promotion Panel
// ---------------------------------------------------------------------------

function LearningPanel() {
  const { user } = useAuth();
  const canApprove = user ? can.approvPromotion(user.role) : false;
  const [job, setJob] = useState<LatestJobResponse | null>(null);
  const [manifest, setManifest] = useState<BufferManifestResponse | null>(null);
  const [evalResult, setEvalResult] = useState<EvalResponse | null>(null);
  const [checklist, setChecklist] = useState<PromotionChecklistResponse | null>(null);
  const [approving, setApproving] = useState(false);
  const [loadingJob, setLoadingJob] = useState(true);

  useEffect(() => {
    api.latestLearningJob().then((latest) => {
      setJob(latest);
      setLoadingJob(false);
      if (!latest) return;
      api.learningManifest(latest.job_id).then(setManifest).catch(() => {});
      if (latest.model_version) {
        api.learningEval(latest.job_id).then(setEvalResult).catch(() => {});
        api.promotionChecklist(latest.model_version).then(setChecklist).catch(() => {});
      }
    }).catch(() => setLoadingJob(false));
  }, []);

  const handleApprove = async () => {
    if (!job?.model_version) return;
    setApproving(true);
    try {
      const result = await api.approvePromotion(job.model_version, OPERATOR_ID);
      toast[result.approved ? "success" : "error"](result.message);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Promotion failed");
    } finally {
      setApproving(false);
    }
  };

  if (loadingJob) return <Skeleton className="h-64 w-full rounded-xl" />;

  if (!job) return (
    <Card>
      <CardContent className="py-12 text-center">
        <BookOpen className="size-8 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm font-medium">No retrain jobs yet</p>
        <p className="text-xs text-muted-foreground mt-1">Results appear once a job has completed.</p>
      </CardContent>
    </Card>
  );

  const STATUS_COLORS: Record<string, string> = {
    promoted: "text-live",
    eval_complete: "text-primary",
    running: "text-warn",
    failed: "text-destructive",
  };

  return (
    <div className="space-y-4">
      {/* Job status */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center justify-between">
            <span>Retrain job — <span className="font-mono text-xs">{job.job_id}</span></span>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className={cn("text-xs", STATUS_COLORS[job.status] ?? "text-muted-foreground")}>
                {job.status}
              </Badge>
              {job.trigger && <Badge variant="outline" className="text-xs">{job.trigger}</Badge>}
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Dates */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <p className="text-muted-foreground mb-0.5">Started</p>
              <p className="tabular-nums">{new Date(job.created_at).toLocaleString("en-IN")}</p>
            </div>
            {job.completed_at && (
              <div>
                <p className="text-muted-foreground mb-0.5">Completed</p>
                <p className="tabular-nums">{new Date(job.completed_at).toLocaleString("en-IN")}</p>
              </div>
            )}
          </div>

          {/* Buffer manifest — 80/20 composition */}
          {manifest && (
            <>
              <Separator />
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Replay buffer (80% recent / 20% anchor)</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md bg-muted/60 px-3 py-2">
                    <p className="text-xs text-muted-foreground mb-0.5">Recent events</p>
                    <p className="font-semibold tabular-nums">{manifest.recent_count.toLocaleString()}
                      <span className="text-xs font-normal text-muted-foreground ml-1">({(manifest.recent_pct * 100).toFixed(0)}%)</span>
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">target ≥80%</p>
                  </div>
                  <div className="rounded-md bg-muted/60 px-3 py-2">
                    <p className="text-xs text-muted-foreground mb-0.5">Anchor slice</p>
                    <p className="font-semibold tabular-nums">{manifest.anchor_count.toLocaleString()}
                      <span className="text-xs font-normal text-muted-foreground ml-1">({(manifest.anchor_pct * 100).toFixed(0)}%)</span>
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">target ~20%</p>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${manifest.recent_pct * 100}%` }} />
                </div>
              </div>
            </>
          )}

          {/* Accuracy gate */}
          {evalResult && (
            <>
              <Separator />
              <div className="space-y-3">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Accuracy gate (94% threshold)</p>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Model accuracy</span>
                    <span className={cn("font-mono font-medium", evalResult.accuracy >= evalResult.accuracy_gate ? "text-live" : "text-destructive")}>
                      {(evalResult.accuracy * 100).toFixed(1)}% / {(evalResult.accuracy_gate * 100).toFixed(0)}% gate
                    </span>
                  </div>
                  <Progress value={Math.min(evalResult.accuracy * 100, 100)} className="h-2" />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  {evalResult.anchor_accuracy != null && (
                    <div className="rounded-md bg-muted/60 px-3 py-2">
                      <p className="text-[10px] text-muted-foreground mb-0.5">Anchor accuracy</p>
                      <p className="text-sm font-semibold">{(evalResult.anchor_accuracy * 100).toFixed(1)}%</p>
                    </div>
                  )}
                  {evalResult.anchor_regression != null && (
                    <div className="rounded-md bg-muted/60 px-3 py-2">
                      <p className="text-[10px] text-muted-foreground mb-0.5">Anchor regression</p>
                      <p className={cn("text-sm font-semibold", Math.abs(evalResult.anchor_regression) > 0.02 ? "text-destructive" : "text-live")}>
                        {evalResult.anchor_regression > 0 ? "+" : ""}{(evalResult.anchor_regression * 100).toFixed(2)}%
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Promotion checklist */}
      {checklist && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center justify-between">
              <span>Promotion gates — <span className="font-mono text-xs">{checklist.model_version}</span></span>
              {checklist.all_complete
                ? <Badge variant="outline" className="text-xs bg-live/10 text-live border-live/30 gap-1"><CheckCircle2 className="size-3" />All gates passed</Badge>
                : <Badge variant="outline" className="text-xs bg-destructive/10 text-destructive border-destructive/30 gap-1"><XCircle className="size-3" />Gates incomplete</Badge>}
            </CardTitle>
            <CardDescription className="text-xs">
              All three gates must pass before this model version can be promoted to production.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              {checklist.items.map((item) => (
                <div key={item.item} className="flex items-start gap-2.5">
                  {item.complete
                    ? <CheckCircle2 className="size-4 text-live shrink-0 mt-0.5" />
                    : <XCircle className="size-4 text-destructive shrink-0 mt-0.5" />}
                  <div>
                    <p className="text-xs font-medium">{item.item}</p>
                    {item.detail && <p className="text-[10px] text-muted-foreground mt-0.5">{item.detail}</p>}
                  </div>
                </div>
              ))}
            </div>
            <Separator />
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                {checklist.all_complete
                  ? "All gates passed — model is ready for promotion."
                  : "Resolve failing gates before promoting. Promotion with incomplete checklist is blocked by the backend."}
              </p>
              <Button
                size="sm"
                disabled={!checklist.all_complete || approving || !canApprove}
                title={!canApprove ? "Admin role required" : undefined}
                className="shrink-0 gap-1.5"
                onClick={handleApprove}
              >
                {approving ? <RefreshCw className="size-3 animate-spin" /> : <CheckCircle2 className="size-3" />}
                Approve promotion
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function GovernancePage() {
  return (
    <div className="flex flex-col h-full">
      <AppHeader title="Governance" />
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-5xl mx-auto space-y-5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300">

          {/* Plain-English explainer — always visible */}
          <div id="tour-governance-tier" className="rounded-xl border border-border/60 bg-muted/30 p-4 space-y-3">
            <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Shield className="size-3.5 text-primary" />
              How the system tiers work
              <InfoPopover
                title="Governance tiers"
                description="The system automatically degrades to a safer mode when components fail, then recovers when they're healthy again. Admins can manually force a tier at any time."
              />
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="rounded-lg border border-live/30 bg-live/5 px-3 py-2.5">
                <p className="font-semibold text-live mb-1">Tier 1 — Full AI</p>
                <p className="text-muted-foreground leading-relaxed">All systems healthy. The AI solver (MILP) finds the optimal dispatch within 1.5 seconds. If it times out, a fast greedy fallback kicks in automatically. This is normal operating mode.</p>
              </div>
              <div className="rounded-lg border border-warn/30 bg-warn/5 px-3 py-2.5">
                <p className="font-semibold text-warn mb-1">Tier 2 — Rule-based</p>
                <p className="text-muted-foreground leading-relaxed">The AI impact model or live data APIs are partially down. The AI switches to simpler rule-based scoring instead. Recommendations are less precise but still reliable. Usually recovers automatically.</p>
              </div>
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5">
                <p className="font-semibold text-destructive mb-1">Tier 3 — Manual SOP</p>
                <p className="text-muted-foreground leading-relaxed">Major outage — both data ingestion and feature services are down. The system falls back to static Standard Operating Procedure templates. Commanders operate manually; all actions are audit-logged.</p>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground">
              <span className="font-medium">Shadow mode</span> — when enabled, the AI produces recommendations but does not act on them. Useful for validating a new model version against live outcomes before promoting it to production.
            </p>
          </div>

          {/* Tier control panel — always visible */}
          <TierControlPanel />

          {/* Tabs */}
          <Tabs defaultValue="health">
            <TabsList className="grid w-full grid-cols-4 max-w-lg">
              <TabsTrigger value="health" className="gap-1.5">
                <Activity className="size-3.5" />
                Health
              </TabsTrigger>
              <TabsTrigger value="audit" className="gap-1.5">
                <History className="size-3.5" />
                Audit log
              </TabsTrigger>
              <TabsTrigger value="drills" className="gap-1.5">
                <Zap className="size-3.5" />
                Drills
              </TabsTrigger>
              <TabsTrigger value="learning" className="gap-1.5">
                <BookOpen className="size-3.5" />
                Learning
              </TabsTrigger>
            </TabsList>

            <TabsContent value="health" className="mt-5"><HealthPanel /></TabsContent>
            <TabsContent value="audit" className="mt-5"><AuditPanel /></TabsContent>
            <TabsContent value="drills" className="mt-5"><DrillsPanel /></TabsContent>
            <TabsContent value="learning" className="mt-5"><LearningPanel /></TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
