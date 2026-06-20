import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AnalyticsPage() {
  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-lg font-semibold mb-4">Citizen triage</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Citizen reporting service not yet available</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          M17 CitizenReportService has not been implemented yet — photo submissions, ICT-band
          triage, and verify/reject workflows for source=CITIZEN events will appear here once
          that module ships.
        </CardContent>
      </Card>
    </div>
  );
}
