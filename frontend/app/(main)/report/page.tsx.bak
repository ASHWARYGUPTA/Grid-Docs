"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AppHeader } from "@/components/app-header";
import { getOrCreateUserRef, addRecentReport, readRecentReports, readSubscriptions } from "@/lib/citizen-storage";
import type { StoredReport, StoredSubscription } from "@/lib/citizen-storage";
import { useDashboardSocket } from "@/lib/ws";
import type { CitizenPreAlertPayload, CitizenReport } from "@/lib/types";
import { RecentReports } from "./_components/recent-reports";
import { ReportForm } from "./_components/report-form";
import { ReportResult } from "./_components/report-result";
import { matchesSubscription, SubscriptionManager } from "./_components/subscription-manager";

export default function ReportPage() {
  const [userRef, setUserRef] = useState<string | null>(null);
  const [lastReport, setLastReport] = useState<CitizenReport | null>(null);
  const [recentReports, setRecentReports] = useState<StoredReport[]>([]);
  const [subscriptions, setSubscriptions] = useState<StoredSubscription[]>([]);
  const { lastDelta } = useDashboardSocket();

  useEffect(() => {
    setUserRef(getOrCreateUserRef());
    setRecentReports(readRecentReports());
    setSubscriptions(readSubscriptions());
  }, []);

  useEffect(() => {
    if (!lastDelta || lastDelta.scope !== "citizen") return;
    const payload = lastDelta.payload as { type?: string };
    if (payload.type !== "CitizenPreAlert") return;
    const alert = lastDelta.payload as unknown as CitizenPreAlertPayload;
    if (!matchesSubscription(alert, subscriptions)) return;
    const message = `${alert.alert_type === "hotspot" ? "Hotspot" : "Congestion building"} near your subscribed corridor`;
    if (alert.severity_band === "Orange") toast.error(message);
    else toast.warning(message);
  }, [lastDelta, subscriptions]);

  function handleSubmitted(report: CitizenReport) {
    setLastReport(report);
    const stored: StoredReport = {
      report_id: report.report_id,
      corridor: report.corridor,
      created_at: report.created_at,
    };
    addRecentReport(stored);
    setRecentReports(readRecentReports());
  }

  if (userRef === null) return null;

  return (
    <div className="flex flex-col h-full">
      <AppHeader title="Citizen Report" />

      <div className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-2xl mx-auto space-y-5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300">
          <ReportForm onSubmitted={handleSubmitted} />
          {lastReport && <ReportResult report={lastReport} />}
          <SubscriptionManager
            userRef={userRef}
            subscriptions={subscriptions}
            onSubscriptionsChange={setSubscriptions}
          />
          <RecentReports reports={recentReports} />
        </div>
      </div>
    </div>
  );
}
