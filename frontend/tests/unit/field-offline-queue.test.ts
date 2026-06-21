import { describe, expect, it, vi, beforeEach } from "vitest";
import { drainQueue, enqueueClosure, readQueue } from "@/lib/field-offline-queue";
import { api } from "@/lib/api";
import type { ClosureRequest } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: { fieldClose: vi.fn() },
}));

function makeRequest(): ClosureRequest {
  return {
    closed_datetime: "2024-01-01T00:00:00Z",
    barricades_used: 1,
    officers_used: 1,
    diversion_activated: false,
    notes: null,
    officer_id: "OFF-1",
  };
}

describe("field-offline-queue", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(api.fieldClose).mockReset();
  });

  it("enqueues a closure when persisted", () => {
    enqueueClosure("EVT1", makeRequest());
    const queue = readQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0].eventId).toBe("EVT1");
  });

  it("drains and removes entries that sync successfully", async () => {
    vi.mocked(api.fieldClose).mockResolvedValue({
      event_id: "EVT1",
      closure_id: "FCLOSE-1",
      event_closed: true,
      closed_datetime: "2024-01-01T00:00:00Z",
      queued_offline: false,
    });
    enqueueClosure("EVT1", makeRequest());

    const result = await drainQueue();
    expect(result).toEqual({ synced: 1, remaining: 0 });
    expect(readQueue()).toHaveLength(0);
  });

  it("keeps entries queued when sync continues to fail", async () => {
    vi.mocked(api.fieldClose).mockRejectedValue(new Error("network error"));
    enqueueClosure("EVT1", makeRequest());

    const result = await drainQueue();
    expect(result).toEqual({ synced: 0, remaining: 1 });
    expect(readQueue()).toHaveLength(1);
  });

  it("returns zero/zero when the queue is empty", async () => {
    const result = await drainQueue();
    expect(result).toEqual({ synced: 0, remaining: 0 });
    expect(api.fieldClose).not.toHaveBeenCalled();
  });
});
