import type {
  AckResponse,
  ActionCard,
  BufferManifestResponse,
  CellHistorySummary,
  CitizenReport,
  CitizenReportStatusResponse,
  ClosureRequest,
  ClosureResponse,
  DensityHotspotsResponse,
  DrillResult,
  EvalResponse,
  FieldPacket,
  GovernanceTierResponse,
  HealthRollup,
  LatestJobResponse,
  ObservedHotspotsResponse,
  PlannedEventPackage,
  PredictedHotspotsResponse,
  PropagationMap,
  QueueResponse,
  ScenarioResponse,
  SubscriptionRequest,
  SubscriptionResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  queue: (severity?: string) =>
    request<QueueResponse>(`/recommendations/queue${severity ? `?severity=${severity}` : ""}`),

  card: (eventId: string, mode: "skeleton" | "complete" | "auto" = "complete") =>
    request<ActionCard>(`/recommendations/${eventId}?mode=${mode}`),

  refreshCard: (eventId: string) =>
    request<ActionCard>(`/recommendations/${eventId}/refresh`, { method: "POST" }),

  approve: (cardId: string, commanderId: string, overrideCodes: string[] = []) =>
    request<{ message: string }>(`/recommendations/${cardId}/approve`, {
      method: "POST",
      body: JSON.stringify({ commander_id: commanderId, override_codes: overrideCodes }),
    }),

  reject: (cardId: string, commanderId: string, reasonCode: string, notes?: string) =>
    request<{ message: string }>(`/recommendations/${cardId}/reject`, {
      method: "POST",
      body: JSON.stringify({ commander_id: commanderId, reason_code: reasonCode, notes }),
    }),

  hotspotsObserved: () => request<ObservedHotspotsResponse>("/hotspots/observed"),

  hotspotsDensity: (minCount = 1) =>
    request<DensityHotspotsResponse>(`/hotspots/density?min_count=${minCount}`),

  hotspotsPredicted: (horizonHours = 4) =>
    request<PredictedHotspotsResponse>(`/hotspots/predicted?horizon_hours=${horizonHours}`),

  hotspotsCell: (h3Res7: string) =>
    request<CellHistorySummary>(`/hotspots/cell/${h3Res7}`),

  propagationActive: () => request<PropagationMap[]>("/propagation/active"),

  diversionScenarios: (eventId: string) =>
    request<ScenarioResponse>(`/diversions/scenarios/${eventId}`),

  governanceTier: () => request<GovernanceTierResponse>("/governance/tier"),

  governanceHealth: () => request<HealthRollup>("/governance/health"),

  overrideTier: (tier: "1" | "2" | "3", reason: string, operatorId: string) =>
    request<GovernanceTierResponse>("/governance/override-tier", {
      method: "POST",
      body: JSON.stringify({ tier, reason, operator_id: operatorId }),
    }),

  setShadowMode: (enabled: boolean, operatorId: string) =>
    request<GovernanceTierResponse>("/governance/shadow-mode", {
      method: "POST",
      body: JSON.stringify({ enabled, operator_id: operatorId }),
    }),

  triggerCascadeDrill: (concurrentClosures = 5, forceMilpTimeout = true) =>
    request<DrillResult>("/governance/drills/cascade", {
      method: "POST",
      body: JSON.stringify({
        drill_type: "cascade",
        concurrent_closures: concurrentClosures,
        force_milp_timeout: forceMilpTimeout,
      }),
    }),

  lastCascadeDrill: () =>
    request<DrillResult | null>("/governance/drills/cascade/last").catch(() => null),

  latestLearningJob: () =>
    request<LatestJobResponse | null>("/learning/jobs/latest").catch(() => null),

  learningManifest: (jobId: string) =>
    request<BufferManifestResponse>(`/learning/buffer/manifest/${jobId}`),

  learningEval: (jobId: string) => request<EvalResponse>(`/learning/eval/${jobId}`),

  dispatchRoster: () => request<Record<string, unknown>>("/dispatch/roster"),

  plannedUpcoming: (hours = 72) =>
    request<PlannedEventPackage[]>(`/planned/upcoming?hours=${hours}`),

  fieldPacket: (recommendationId: string) =>
    request<FieldPacket>(`/field/packet/${recommendationId}`),

  fieldAck: (recommendationId: string, officerId: string) =>
    request<AckResponse>(`/field/ack/${recommendationId}`, {
      method: "POST",
      body: JSON.stringify({ officer_id: officerId }),
    }),

  fieldClose: (eventId: string, closure: ClosureRequest) =>
    request<ClosureResponse>(`/field/close/${eventId}`, {
      method: "POST",
      body: JSON.stringify(closure),
    }),

  fieldTier: () => request<GovernanceTierResponse>("/field/tier"),

  citizenReport: async (formData: FormData) => {
    const res = await fetch(`${API_URL}/citizen/report`, {
      method: "POST",
      body: formData,
      cache: "no-store",
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail ?? `POST /citizen/report failed: ${res.status}`);
    }
    return res.json() as Promise<CitizenReport>;
  },

  citizenReportStatus: (reportId: string) =>
    request<CitizenReportStatusResponse>(`/citizen/report/${reportId}`),

  citizenSubscribe: (body: SubscriptionRequest) =>
    request<SubscriptionResponse>("/citizen/subscribe", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  citizenUnsubscribe: (subscriptionId: string) =>
    request<{ subscription_id: string; status: string }>(
      `/citizen/subscribe/${subscriptionId}`,
      { method: "DELETE" }
    ),
};
