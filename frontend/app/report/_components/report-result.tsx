import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CitizenReport, CitizenReportStatus } from "@/lib/types";

export function formatIctQuote(p50: number, p80: number): { typical: string; worst: string } {
  return {
    typical: `Typical clearance: ~${p50.toFixed(1)}h`,
    worst: `Worst case: up to ~${p80.toFixed(1)}h`,
  };
}

const STATUS_LABEL: Record<CitizenReportStatus, string> = {
  pending: "Pending review",
  verified: "Verified",
  rejected: "Rejected",
};

interface ReportResultProps {
  report: CitizenReport;
}

export function ReportResult({ report }: ReportResultProps) {
  const ict = formatIctQuote(report.ict_p50, report.ict_p80);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center justify-between">
          <span>Report submitted</span>
          <Badge variant="outline">{STATUS_LABEL[report.status]}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p>{report.corridor ?? "Unmatched corridor"}</p>
        <p className="text-xs text-muted-foreground">H3 cell: {report.h3_cell}</p>
        <p>{ict.typical}</p>
        <p>{ict.worst}</p>
        <p className="text-xs text-muted-foreground">
          Likely cause: {report.cause_hint.replace(/_/g, " ")}
        </p>
      </CardContent>
    </Card>
  );
}
