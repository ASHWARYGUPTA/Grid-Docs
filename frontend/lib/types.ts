// Mirrors backend Pydantic schemas — see backend/src/grid_unlocked/*/schemas.py

export type SeverityBand = "Green" | "Yellow" | "Orange" | "Red";
export type AlertPriority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type CardStatus = "partial" | "complete" | "approved" | "rejected" | "executed";
export type DispatchSource = "MILP" | "GREEDY_FALLBACK";
export type Tier = "1" | "2" | "3";

export interface ModelVersions {
  closure: string;
  ict: string;
  source: string;
}

export interface ImpactScore {
  event_id: string;
  p_closure: number;
  ict_p20_h: number;
  ict_p50_h: number;
  ict_p80_h: number;
  rci: number;
  severity_band: SeverityBand;
  priority_structural: boolean;
  staging_recommended: boolean;
  model_versions: ModelVersions;
  latency_ms: number;
  scored_at: string;
}

export interface PropagationSummary {
  cascade_risk: number;
  seed_rci: number;
  affected_nodes: number;
  max_hop: number;
}

export interface HotspotContext {
  nearby_cluster_count: number;
  cell_event_count_24h: number | null;
  h3_res7: string | null;
}

export interface Assignment {
  station_id: string;
  [key: string]: unknown;
}

export interface DispatchSection {
  recommendation_id: string;
  source: DispatchSource;
  assignments: Assignment[];
  solver_ms: number;
  provenance: string;
}

export interface PlannedSection {
  template_id: string;
  barricade_count: number;
  staffing_min: number;
  staffing_max: number;
  barricade_staging_required: boolean;
}

export interface GovernanceInfo {
  tier: string;
  shadow_mode: boolean;
  manual_mode: boolean;
}

export interface EvidenceBundle {
  top_features: Record<string, number | string>[];
  model_versions: ModelVersions;
  diversion_routes: DiversionRoute[];
}

export interface ActionCard {
  card_id: string;
  event_id: string;
  source: string;
  status: CardStatus;
  alert_priority: AlertPriority;
  impact: ImpactScore;
  propagation: PropagationSummary;
  hotspot_context: HotspotContext;
  diversions: DiversionRoute[];
  auto_suggest_diversion: boolean;
  dispatch: DispatchSection | null;
  dispatch_pending: boolean;
  planned: PlannedSection | null;
  evidence: EvidenceBundle;
  governance: GovernanceInfo;
  provenance: Record<string, string>;
  skeleton_ms: number;
  latency_ms: number;
  field_packet_link: string | null;
  created_at: string;
  updated_at: string;
}

export interface QueueItem {
  event_id: string;
  card_id: string | null;
  rci: number;
  p_closure: number;
  severity_band: SeverityBand;
  alert_priority: AlertPriority;
  corridor: string | null;
  status: CardStatus | null;
}

export interface QueueResponse {
  items: QueueItem[];
  count: number;
}

export interface GovernanceTierResponse {
  tier: Tier;
  shadow_mode: boolean;
  manual_mode: boolean;
  flags: Record<string, boolean>;
  updated_at: string;
  updated_by: string | null;
}

export interface ModuleHealth {
  module: string;
  status: "healthy" | "degraded" | "down";
  detail: string;
  metrics: Record<string, number | string | boolean>;
}

export interface HealthRollup {
  overall_status: "healthy" | "degraded" | "down";
  tier: Tier;
  shadow_mode: boolean;
  modules: ModuleHealth[];
  checked_at: string;
}

export interface DrillResult {
  id: number;
  drill_type: string;
  passed: boolean;
  concurrent_closures: number;
  fallback_rate: number;
  max_latency_ms: number;
  deadline_ms: number;
  detail: string;
  created_at: string;
}

export interface LatestJobResponse {
  job_id: string;
  status: "pending" | "running" | "eval_complete" | "promoted" | "failed";
  trigger: "scheduled" | "drift" | "manual";
  model_version: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface BufferManifestResponse {
  job_id: string;
  status: string;
  recent_count: number;
  anchor_count: number;
  recent_pct: number;
  anchor_pct: number;
  window_weeks: number;
  strata: Record<string, number>;
  reject_reason_counts: Record<string, number>;
  created_at: string;
}

export interface EvalResponse {
  job_id: string;
  model_version: string;
  accuracy: number;
  anchor_accuracy: number;
  incumbent_anchor_accuracy: number | null;
  anchor_regression: number | null;
  gate_passed: boolean;
  anchor_stable: boolean;
  accuracy_gate: number;
  anchor_epsilon: number;
}

export interface HotspotCluster {
  cluster_id: string;
  layer: "observed" | "predicted";
  centroid_lat: number;
  centroid_lon: number;
  density: number;
  cause_entropy: number;
  h3_cells: string[];
  corridors: string[];
  persistence_score: number;
  label: string | null;
}

export interface ObservedHotspotsResponse {
  clusters: HotspotCluster[];
  refreshed_at: string;
  latency_ms: number;
  source: string;
}

export interface CellDensityPoint {
  h3_res7: string;
  centroid_lat: number;
  centroid_lon: number;
  count: number;
}

export interface DensityHotspotsResponse {
  cells: CellDensityPoint[];
  refreshed_at: string;
  latency_ms: number;
  source: string;
}

export interface CellHistorySummary {
  h3_res7: string;
  total_events: number;
  events_30d: number;
  persistence_score: number;
  top_causes: { cause: string; count: number }[];
  top_corridors: { corridor: string; count: number }[];
  hourly_counts: number[];
  centroid_lat: number;
  centroid_lon: number;
}

export interface PredictedZoneForecast {
  corridor: string;
  zone: string | null;
  expected_count: number;
  baseline_count: number;
  lift_pct: number;
  centroid_lat: number | null;
  centroid_lon: number | null;
}

export interface PredictedHotspotsResponse {
  horizon_hours: number;
  forecasts: PredictedZoneForecast[];
  refreshed_at: string;
  latency_ms: number;
  source: string;
}

export interface PropagationNode {
  node_id: string;
  corridor: string | null;
  risk: number;
  hop: number;
  parent_edge: string | null;
}

export interface PropagationMap {
  event_id: string;
  seed_node_id: string;
  seed_rci: number;
  nodes: PropagationNode[];
  cascade_risk: number;
  latency_ms: number;
}

export interface DiversionRoute {
  rank: number;
  junction_id: string;
  description: string;
  route_summary: string;
  path: string[];
  eta_delta_min: number;
  capacity_class: string;
  gridlock_cycle_detected: boolean;
  edge_disjoint: boolean;
}

export interface ScenarioResponse {
  event_id: string;
  corridor: string | null;
  junction_id: string;
  p_closure: number;
  is_peak_hour: boolean;
  auto_suggest: boolean;
  routes: DiversionRoute[];
  latency_ms: number;
}

export interface ChecklistItem {
  id: string;
  category: string;
  description: string;
  required: boolean;
}

export interface ImpactOverlay {
  p_closure: number;
  ict_p20_h: number;
  ict_p50_h: number;
  ict_p80_h: number;
  rci: number;
  severity_band: string;
  severity_ordinal: number;
  source: string;
}

export interface PlannedEventPackage {
  event_id: string;
  template_id: string;
  cause: string;
  corridor: string | null;
  hours_until_start: number;
  estimated_duration_h: number | null;
  staffing_min: number;
  staffing_max: number;
  barricade_count: number;
  barricade_staging_required: boolean;
  deployment_lead_time_hours: number;
  checklist: ChecklistItem[];
  impact_overlay: ImpactOverlay;
  compliance_items: string[];
  low_confidence_template: boolean;
  cached: boolean;
  latency_ms: number;
  generated_at: string;
}

export type DeltaScope = "card" | "tier" | "hotspot" | "citizen" | "field";

export interface DashboardDelta {
  type: "dashboard.delta";
  scope: DeltaScope;
  event_id: string | null;
  payload: Record<string, unknown>;
  emitted_at: string;
}

export interface FieldAssignmentSummary {
  unit_id: string;
  station_id: string;
  equip_type: string;
  eta_min: number;
  rci: number;
  cascade_risk: number;
  needs_heavy_tow: boolean;
}

export interface FieldDiversionSummary {
  junction_id: string;
  description: string;
  route_summary: string;
  eta_delta_min: number;
  capacity_class: string;
  available: boolean;
}

export interface FieldIctBands {
  ict_p20_h: number;
  ict_p50_h: number;
  ict_p80_h: number;
  severity_band: string;
}

export interface FieldPacket {
  recommendation_id: string;
  event_id: string;
  source: DispatchSource;
  tier_at_decision: Tier;
  assignments: FieldAssignmentSummary[];
  impact: FieldIctBands;
  top_diversion: FieldDiversionSummary | null;
  navigation_deep_link: string;
  event_status: string;
  already_closed: boolean;
  acknowledged: boolean;
  acknowledged_at: string | null;
  provenance: Record<string, string>;
  generated_at: string;
}

export interface AckResponse {
  recommendation_id: string;
  acknowledged: boolean;
  acknowledged_at: string;
}

export interface ClosureRequest {
  closed_datetime: string;
  barricades_used: number;
  officers_used: number;
  diversion_activated: boolean;
  notes: string | null;
  officer_id: string;
}

export interface ClosureResponse {
  event_id: string;
  closure_id: string;
  event_closed: boolean;
  closed_datetime: string;
  queued_offline: boolean;
}

export type CitizenReportStatus = "pending" | "verified" | "rejected";

export interface CitizenReport {
  report_id: string;
  status: CitizenReportStatus;
  h3_cell: string;
  corridor: string | null;
  junction: string | null;
  ict_p50: number;
  ict_p80: number;
  p_closure: number;
  cause_hint: string;
  cause_confidence: number;
  event_id: string | null;
  has_photo: boolean;
  created_at: string;
}

export interface CitizenReportStatusResponse {
  report_id: string;
  status: CitizenReportStatus;
  ict_p50: number;
  ict_p80: number;
  p_closure: number;
  corridor: string | null;
  h3_cell: string;
  created_at: string;
}

export interface SubscriptionRequest {
  user_ref: string;
  corridors: string[];
  h3_cells: string[];
}

export interface SubscriptionResponse {
  subscription_id: string;
  user_ref: string;
  corridors: string[];
  h3_cells: string[];
  created_at: string;
}

export interface CitizenPreAlertPayload {
  type: "CitizenPreAlert";
  subscription_id: string;
  alert_type: "hotspot" | "propagation";
  severity_band: string;
}
