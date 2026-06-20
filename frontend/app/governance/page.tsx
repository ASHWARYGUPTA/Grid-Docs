"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type {
  BufferManifestResponse,
  DrillResult,
  EvalResponse,
  HealthRollup,
  LatestJobResponse,
} from "@/lib/types";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  healthy: "default",
  degraded: "secondary",
  down: "destructive",
};

export default function GovernancePage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <h1 className="text-lg font-semibold">Governance</h1>
      <Tabs defaultValue="health">
        <TabsList>
          <TabsTrigger value="health">Health</TabsTrigger>
          <TabsTrigger value="drills">Drills</TabsTrigger>
          <TabsTrigger value="learning">Learning</TabsTrigger>
        </TabsList>
        <TabsContent value="health">
          <HealthPanel />
        </TabsContent>
        <TabsContent value="drills">
          <DrillsPanel />
        </TabsContent>
        <TabsContent value="learning">
          <LearningPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function HealthPanel() {
  const [health, setHealth] = useState<HealthRollup | null>(null);

  useEffect(() => {
    api
      .governanceHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  if (!health) return <Skeleton className="h-40 w-full mt-4" />;

  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>Module health</span>
          <Badge variant={STATUS_VARIANT[health.overall_status] ?? "outline"}>
            {health.overall_status}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Module</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {health.modules.map((m) => (
              <TableRow key={m.module}>
                <TableCell className="font-medium">{m.module}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[m.status] ?? "outline"}>{m.status}</Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{m.detail}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function DrillsPanel() {
  const [last, setLast] = useState<DrillResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.lastCascadeDrill().then(setLast);
  }, []);

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
    <Card className="mt-4">
      <CardHeader>
        <CardTitle className="text-base">Cascade drill</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button onClick={runDrill} disabled={running}>
          {running ? "Running…" : "Trigger cascade drill"}
        </Button>
        {last && (
          <div className="text-sm space-y-1 border rounded-md p-3">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Result</span>
              <Badge variant={last.passed ? "default" : "destructive"}>
                {last.passed ? "PASSED" : "FAILED"}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Concurrent closures</span>
              <span>{last.concurrent_closures}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Fallback rate</span>
              <span>{(last.fallback_rate * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Max latency</span>
              <span>
                {last.max_latency_ms.toFixed(0)}ms / {last.deadline_ms}ms deadline
              </span>
            </div>
            <p className="text-muted-foreground">{last.detail}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LearningPanel() {
  const [job, setJob] = useState<LatestJobResponse | null>(null);
  const [manifest, setManifest] = useState<BufferManifestResponse | null>(null);
  const [evalResult, setEvalResult] = useState<EvalResponse | null>(null);

  useEffect(() => {
    api.latestLearningJob().then((latest) => {
      setJob(latest);
      if (!latest) return;
      api.learningManifest(latest.job_id).then(setManifest).catch(() => {});
      if (latest.model_version) {
        api.learningEval(latest.job_id).then(setEvalResult).catch(() => {});
      }
    });
  }, []);

  if (!job) {
    return (
      <Card className="mt-4">
        <CardContent className="py-6 text-sm text-muted-foreground">
          No retrain jobs have run yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>Latest retrain — {job.job_id}</span>
          <Badge variant="outline">{job.status}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm space-y-3">
        {manifest && (
          <div>
            <p className="font-medium mb-1">Buffer manifest</p>
            <div className="flex justify-between text-muted-foreground">
              <span>Recent / Anchor</span>
              <span>
                {manifest.recent_count} ({(manifest.recent_pct * 100).toFixed(0)}%) /{" "}
                {manifest.anchor_count} ({(manifest.anchor_pct * 100).toFixed(0)}%)
              </span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>Status</span>
              <span>{manifest.status}</span>
            </div>
          </div>
        )}
        {evalResult && (
          <div>
            <p className="font-medium mb-1">Accuracy gate</p>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Accuracy vs gate</span>
              <span>
                {(evalResult.accuracy * 100).toFixed(1)}% / {(evalResult.accuracy_gate * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Gate passed</span>
              <Badge variant={evalResult.gate_passed ? "default" : "destructive"}>
                {String(evalResult.gate_passed)}
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Anchor stable</span>
              <Badge variant={evalResult.anchor_stable ? "default" : "destructive"}>
                {String(evalResult.anchor_stable)}
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
