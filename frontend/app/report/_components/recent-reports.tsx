"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { StoredReport } from "@/lib/citizen-storage";
import type { CitizenReportStatus } from "@/lib/types";

const STATUS_CONFIG: Record<
  CitizenReportStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  pending: { label: "Pending", variant: "secondary" },
  verified: { label: "Verified", variant: "default" },
  rejected: { label: "Rejected", variant: "destructive" },
};

function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

interface RecentReportsProps {
  reports: StoredReport[];
}

export function RecentReports({ reports }: RecentReportsProps) {
  const [statuses, setStatuses] = useState<Record<string, CitizenReportStatus>>({});

  useEffect(() => {
    reports.forEach((report) => {
      api
        .citizenReportStatus(report.report_id)
        .then((res) => setStatuses((prev) => ({ ...prev, [report.report_id]: res.status })))
        .catch(() => {});
    });
  }, [reports]);

  if (reports.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Clock className="size-4 text-muted-foreground" />
          Your recent reports
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-0 divide-y divide-border">
          {reports.map((report) => {
            const status = statuses[report.report_id] ?? "pending";
            const cfg = STATUS_CONFIG[status];
            return (
              <div
                key={report.report_id}
                className="flex items-center justify-between py-3 gap-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">
                    {report.corridor ?? "Unmatched corridor"}
                  </p>
                  {report.created_at && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {relativeTime(report.created_at)}
                    </p>
                  )}
                </div>
                <Badge variant={cfg.variant} className="text-xs shrink-0">
                  {cfg.label}
                </Badge>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
