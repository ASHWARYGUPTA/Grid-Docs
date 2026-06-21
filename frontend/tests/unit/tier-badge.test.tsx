import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TierBadge } from "@/components/tier-badge";
import { api } from "@/lib/api";
import { useDashboardSocket } from "@/lib/ws";
import type { GovernanceTierResponse } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: { governanceTier: vi.fn() },
}));

vi.mock("@/lib/ws", () => ({
  useDashboardSocket: vi.fn(),
}));

function tierResponse(overrides: Partial<GovernanceTierResponse>): GovernanceTierResponse {
  return {
    tier: "1",
    shadow_mode: false,
    manual_mode: false,
    flags: {},
    updated_at: "2024-01-01T00:00:00Z",
    updated_by: null,
    ...overrides,
  };
}

describe("TierBadge", () => {
  beforeEach(() => {
    vi.mocked(useDashboardSocket).mockReturnValue({ lastDelta: null, connected: true });
  });

  it("shows a placeholder before the tier loads", () => {
    vi.mocked(api.governanceTier).mockReturnValue(new Promise(() => {}));
    render(<TierBadge />);
    expect(screen.getByText("Tier —")).toBeInTheDocument();
  });

  it("renders Tier 1 without shadow mode label", async () => {
    vi.mocked(api.governanceTier).mockResolvedValue(tierResponse({ tier: "1" }));
    render(<TierBadge />);
    await waitFor(() => expect(screen.getByText("Tier 1")).toBeInTheDocument());
  });

  it("appends a shadow mode indicator when shadow_mode is true", async () => {
    vi.mocked(api.governanceTier).mockResolvedValue(
      tierResponse({ tier: "1", shadow_mode: true })
    );
    render(<TierBadge />);
    await waitFor(() => expect(screen.getByText("Tier 1 · Shadow")).toBeInTheDocument());
  });

  it("shows the Tier 3 manual-mode explanation on hover", async () => {
    vi.mocked(api.governanceTier).mockResolvedValue(
      tierResponse({ tier: "3", manual_mode: true })
    );
    render(<TierBadge />);
    await waitFor(() => expect(screen.getByText("Tier 3")).toBeInTheDocument());

    await userEvent.hover(screen.getByText("Tier 3"));
    await waitFor(() =>
      expect(screen.getByText(/manual SOP mode/i)).toBeInTheDocument()
    );
  });

  it("re-fetches the tier when a tier-scoped delta arrives", async () => {
    vi.mocked(api.governanceTier).mockResolvedValue(tierResponse({ tier: "1" }));
    vi.mocked(useDashboardSocket).mockReturnValue({
      lastDelta: {
        type: "dashboard.delta",
        scope: "tier",
        event_id: null,
        payload: { tier: "2" },
        emitted_at: "2024-01-01T00:00:00Z",
      },
      connected: true,
    });
    render(<TierBadge />);
    await waitFor(() => expect(api.governanceTier).toHaveBeenCalled());
  });
});
