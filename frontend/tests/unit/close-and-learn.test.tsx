import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  ActionCardPanel,
  canCloseAndLearn,
} from "@/app/live/_components/action-card-panel";
import type { ActionCard, CardStatus } from "@/lib/types";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    fieldClose: vi.fn(),
    latestLearningJob: vi.fn(),
    learningManifest: vi.fn(),
    transitImpact: vi.fn(),
  },
}));

vi.mock("@/lib/field-offline-queue", () => ({
  enqueueClosure: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

function makeCard(status: CardStatus): ActionCard {
  return {
    card_id: "CARD-1",
    event_id: "EVT-1",
    source: "astram",
    status,
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

describe("canCloseAndLearn", () => {
  it("is true for live (non-rejected) card statuses", () => {
    expect(canCloseAndLearn("complete")).toBe(true);
    expect(canCloseAndLearn("approved")).toBe(true);
    expect(canCloseAndLearn("executed")).toBe(true);
  });

  it("is false for partial and rejected cards", () => {
    expect(canCloseAndLearn("partial")).toBe(false);
    expect(canCloseAndLearn("rejected")).toBe(false);
  });
});

describe("ActionCardPanel Close & Learn", () => {
  beforeEach(() => {
    vi.mocked(api.fieldClose).mockReset();
    vi.mocked(api.latestLearningJob).mockReset();
    // Default: no retrain job yet — surfaceLearningSignal still resolves cleanly.
    vi.mocked(api.latestLearningJob).mockResolvedValue(null);
  });

  afterEach(() => {
    cleanup();
  });

  it("offers the Close & Learn action for a live (complete) card", () => {
    render(<ActionCardPanel card={makeCard("complete")} loading={false} onMutated={() => {}} />);
    expect(screen.getByRole("button", { name: /close & learn/i })).toBeInTheDocument();
  });

  it("hides the Close & Learn action for a rejected card", () => {
    render(<ActionCardPanel card={makeCard("rejected")} loading={false} onMutated={() => {}} />);
    expect(screen.queryByRole("button", { name: /close & learn/i })).toBeNull();
  });

  it("submits the closure through fieldClose and refreshes via onMutated", async () => {
    vi.mocked(api.fieldClose).mockResolvedValue({
      event_id: "EVT-1",
      closure_id: "FCLOSE-1",
      event_closed: true,
      closed_datetime: "2024-01-01T00:00:00Z",
      queued_offline: false,
    });
    const onMutated = vi.fn();
    render(<ActionCardPanel card={makeCard("approved")} loading={false} onMutated={onMutated} />);

    fireEvent.click(screen.getByRole("button", { name: /close & learn/i }));

    const barricades = await screen.findByLabelText("Barricades used");
    fireEvent.change(barricades, { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Officers used"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm closure" }));

    await waitFor(() => expect(api.fieldClose).toHaveBeenCalledTimes(1));
    const [eventId, body] = vi.mocked(api.fieldClose).mock.calls[0];
    expect(eventId).toBe("EVT-1");
    expect(body.barricades_used).toBe(3);
    expect(body.officers_used).toBe(2);
    expect(body.diversion_activated).toBe(true);
    expect(body.officer_id).toBe("CMD-DASHBOARD");
    await waitFor(() => expect(onMutated).toHaveBeenCalled());
  });
});
