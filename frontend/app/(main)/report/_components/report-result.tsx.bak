import { CheckCircle2, Clock, Navigation } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { CitizenReport, CitizenReportStatus } from "@/lib/types";

export function formatIctQuote(p50: number, p80: number): { typical: string; worst: string } {
  return {
    typical: `~${p50.toFixed(1)}h typical clearance`,
    worst: `Up to ~${p80.toFixed(1)}h worst case`,
  };
}

const STATUS_CONFIG: Record<
  CitizenReportStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline";
  }
> = {
  pending: { label: "Pending review", variant: "secondary" },
  verified: { label: "Verified ✓", variant: "default" },
  rejected: { label: "Rejected", variant: "destructive" },
};

interface ReportResultProps {
  report: CitizenReport;
}

export function ReportResult({ report }: ReportResultProps) {
  const ict = formatIctQuote(report.ict_p50, report.ict_p80);
  const cfg = STATUS_CONFIG[report.status];

  return (
    <Card className="border-l-4 border-l-live animate-in fade-in-0 slide-in-from-bottom-2 duration-300">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <CheckCircle2 className="size-4 text-live" />
          Report submitted
          <Badge variant={cfg.variant} className="ml-auto text-xs">
            {cfg.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center gap-2">
          <Navigation className="size-3.5 text-muted-foreground shrink-0" />
          <span className="font-medium">{report.corridor ?? "Unmatched corridor"}</span>
        </div>

        <p className="text-xs text-muted-foreground font-mono bg-muted/50 rounded px-2 py-1">
          H3 cell: {report.h3_cell}
        </p>

        <Separator />

        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="size-3.5 shrink-0" />
            <span>{ict.typical}</span>
          </div>
          <p className="text-xs text-muted-foreground pl-5">{ict.worst}</p>
        </div>

        <p className="text-xs text-muted-foreground capitalize">
          Likely cause:{" "}
          <span className="text-foreground font-medium">
            {report.cause_hint.replace(/_/g, " ")}
          </span>
        </p>
      </CardContent>
    </Card>
  );
}
