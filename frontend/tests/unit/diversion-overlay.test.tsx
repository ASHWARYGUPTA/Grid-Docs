import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { ActionCardPanel } from "@/app/live/_components/action-card-panel";
import type { ActionCard, DiversionRoute } from "@/lib/types";

function makeRoute(overrides: Partial<DiversionRoute>): DiversionRoute {
  return {
    rank: 1,
    junction_id: "JCN-1",
    description: "Via Outer Ring Road",
    route_summary: "ORR -> Silk Board",
    path: ["corridor:orr-east-1", "corridor:hosur-road"],
    waypoints: [
      { lat: 12.93, lng: 77.62, corridor: "ORR East 1" },
      { lat: 12.91, lng: 77.61, corridor: "Hosur Road" },
    ],
    eta_delta_min: 4.2,
    capacity_class: "medium",
    gridlock_cycle_detected: false,
    edge_disjoint: true,
    ...overrides,
  };
}

function makeCard(diversions: DiversionRoute[]): ActionCard {
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
    diversions,
    auto_suggest_diversion: false,
    dispatch: null,
    dispatch_pending: false,
    planned: null,
    evidence: { top_features: [], model_versions: { closure: "lgbm-v1", ict: "cox-ph-v1", source: "ml" }, diversion_routes: diversions },
    governance: { tier: "1", shadow_mode: false, manual_mode: false },
    provenance: {},
    skeleton_ms: 0,
    latency_ms: 10,
    field_packet_link: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };
}

describe("ActionCardPanel diversion route cross-highlight", () => {
  // base-ui's Tabs assigns globally-incrementing element ids, so without an
  // explicit cleanup() a second render() in the next `it` leaves the first
  // render's tablist mounted too — causing getByRole/getByText to match two
  // "Routes" tabs instead of one.
  afterEach(() => {
    cleanup();
  });

  it("calls onHoverRoute with the route's rank on mouse enter and null on leave", () => {
    const onHoverRoute = vi.fn();
    const card = makeCard([makeRoute({ rank: 1 }), makeRoute({ rank: 2, description: "Via Hosur Road" })]);
    render(<ActionCardPanel card={card} loading={false} onMutated={() => {}} onHoverRoute={onHoverRoute} />);

    fireEvent.click(screen.getByRole("tab", { name: "Routes" }));
    const row = screen.getByText("#1 Via Outer Ring Road").closest("div")!.parentElement!;

    fireEvent.mouseEnter(row);
    expect(onHoverRoute).toHaveBeenCalledWith(1);

    fireEvent.mouseLeave(row);
    expect(onHoverRoute).toHaveBeenCalledWith(null);
  });

  it("flags routes with fewer than 2 waypoints as having no map geometry", () => {
    const card = makeCard([makeRoute({ rank: 1, waypoints: [] })]);
    render(<ActionCardPanel card={card} loading={false} onMutated={() => {}} />);

    fireEvent.click(screen.getByRole("tab", { name: "Routes" }));
    expect(screen.getByText("Map geometry unavailable for this route.")).toBeInTheDocument();
  });

  it("does not throw when onHoverRoute is omitted", () => {
    const card = makeCard([makeRoute({ rank: 1 })]);
    render(<ActionCardPanel card={card} loading={false} onMutated={() => {}} />);

    fireEvent.click(screen.getByRole("tab", { name: "Routes" }));
    const row = screen.getByText("#1 Via Outer Ring Road").closest("div")!.parentElement!;
    expect(() => fireEvent.mouseEnter(row)).not.toThrow();
  });
});
