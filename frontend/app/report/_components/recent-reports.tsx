"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { StoredReport } from "@/lib/citizen-storage";
import type { CitizenReportStatus } from "@/lib/types";

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
        <CardTitle className="text-base">Your recent reports</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {reports.map((report) => (
          <div key={report.report_id} className="flex items-center justify-between text-sm">
            <span>{report.corridor ?? "Unmatched corridor"}</span>
            <Badge variant="outline">{statuses[report.report_id] ?? "pending"}</Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
