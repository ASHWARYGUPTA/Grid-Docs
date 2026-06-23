import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { ActionCardPanel } from "@/app/live/_components/action-card-panel";
import type { ActionCard, TransitImpactIndex } from "@/lib/types";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { transitImpact: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

function makeCard(): ActionCard {
  return {
    card_id: "CARD-1",
    event_id: "EVT-1",
    source: "astram",
    status: "complete",
    alert_priority: "HIGH",
    impact: {
      event_id: "EVT-1",
      p_closure: 0.5,
      ict_p20_h: 0.5,
      ict_p50_h: 1,
      ict_p80_h: 2,
      rci: 0.6,
      severity_band: "Orange",
      priority_structural: false,
      staging_recommended: false,
      model_versions: { closure: "lgbm-v1", ict: "cox-ph-v1", source: "ml" },
      latency_ms: 10,
      scored_at: "2024-01-01T00:00:00Z",
    },
    propagation: { cascade_risk: 0.3, seed_rci: 0.6, affected_nodes: 2, max_hop: 1 },
    hotspot_context: { nearby_cluster_count: 0, cell_event_count_24h: null, h3_res7: null },
    diversions: [],
    auto_suggest_diversion: false,
    dispatch: null,
    dispatch_pending: false,
    planned: null,
    evidence: {
      top_features: [],
      model_versions: { closure: "lgbm-v1", ict: "cox-ph-v1", source: "ml" },
      diversion_routes: [],
    },
    governance: { tier: "1", shadow_mode: false, manual_mode: false },
    provenance: {},
    skeleton_ms: 0,
    latency_ms: 10,
    field_packet_link: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };
}

const TRANSIT: TransitImpactIndex = {
  event_id: "EVT-1",
  corridor: "Mysore Road",
  tier: "1",
  degraded: false,
  advisory_only: true,
  passenger_delay_index: 0.42,
  transfer_overload_risk: 0.18,
  affected_routes: [
    {
      route_id: "R1",
      name: "365 Majestic-Kengeri",
      occupancy: 80,
      predicted_delay_min: 7.5,
      overlap_fraction: 0.6,
    },
  ],
  advisory_message: "Expect crowding on route 365.",
  cached: false,
  latency_ms: 5,
  generated_at: "2024-01-01T00:00:00Z",
};

describe("ActionCardPanel Transit tab", () => {
  beforeEach(() => {
    vi.mocked(api.transitImpact).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("lazy-loads M12 transit impact only when the Transit tab is opened", async () => {
    vi.mocked(api.transitImpact).mockResolvedValue(TRANSIT);
    render(<ActionCardPanel card={makeCard()} loading={false} onMutated={() => {}} />);

    // The default (Impact) tab must not trigger a transit fetch.
    expect(api.transitImpact).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: "Transit" }));

    expect(await screen.findByText("365 Majestic-Kengeri")).toBeInTheDocument();
    expect(api.transitImpact).toHaveBeenCalledWith("EVT-1");
    expect(api.transitImpact).toHaveBeenCalledTimes(1);
  });
});
