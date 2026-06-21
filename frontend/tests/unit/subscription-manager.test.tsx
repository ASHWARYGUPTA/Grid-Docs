import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import {
  SubscriptionManager,
  matchesSubscription,
} from "@/app/report/_components/subscription-manager";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { citizenSubscribe: vi.fn(), citizenUnsubscribe: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

describe("matchesSubscription", () => {
  it("matches when subscription_id is present in the list", () => {
    const subs = [{ subscription_id: "SUB-1", corridors: ["Mysore Road"] }];
    expect(matchesSubscription({ subscription_id: "SUB-1" }, subs)).toBe(true);
    expect(matchesSubscription({ subscription_id: "SUB-2" }, subs)).toBe(false);
  });
});

describe("SubscriptionManager", () => {
  beforeEach(() => {
    vi.mocked(api.citizenSubscribe).mockReset();
    vi.mocked(api.citizenUnsubscribe).mockReset();
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("subscribes to the selected corridor and calls onSubscriptionsChange", async () => {
    vi.mocked(api.citizenSubscribe).mockResolvedValue({
      subscription_id: "SUB-1",
      user_ref: "CTZUSER-1",
      corridors: ["Airport New South Road"],
      h3_cells: [],
      created_at: "2024-01-01T00:00:00Z",
    });
    const onChange = vi.fn();
    render(
      <SubscriptionManager userRef="CTZUSER-1" subscriptions={[]} onSubscriptionsChange={onChange} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Subscribe" }));

    await waitFor(() => expect(api.citizenSubscribe).toHaveBeenCalledTimes(1));
    const [body] = vi.mocked(api.citizenSubscribe).mock.calls[0];
    expect(body.user_ref).toBe("CTZUSER-1");
    expect(body.h3_cells).toEqual([]);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
  });

  it("removes a subscription and calls onSubscriptionsChange with it excluded", async () => {
    vi.mocked(api.citizenUnsubscribe).mockResolvedValue({ subscription_id: "SUB-1", status: "unsubscribed" });
    const onChange = vi.fn();
    const subs = [{ subscription_id: "SUB-1", corridors: ["Mysore Road"] }];
    render(
      <SubscriptionManager userRef="CTZUSER-1" subscriptions={subs} onSubscriptionsChange={onChange} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove Mysore Road subscription" }));

    await waitFor(() => expect(api.citizenUnsubscribe).toHaveBeenCalledWith("SUB-1"));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([]));
  });
});
