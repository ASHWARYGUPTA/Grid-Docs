import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AnalyticsPage() {
  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-lg font-semibold mb-4">Citizen triage</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Commander triage UI not yet built</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          M17 CitizenReportService and M18 CitizenApp are implemented — commuters can submit
          photo+GPS reports at <code>/report</code>, and the backend exposes{" "}
          <code>POST /citizen/verify/{"{report_id}"}</code> /{" "}
          <code>POST /citizen/reject/{"{report_id}"}</code>. A dedicated commander-facing panel
          surfacing pending citizen reports on this dashboard has not been built yet — that
          integration remains a gap.
        </CardContent>
      </Card>
    </div>
  );
}
