import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { useDashboardSocket } from "@/lib/ws";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.closed = true;
    this.onclose?.();
  }

  triggerOpen() {
    this.onopen?.();
  }

  triggerMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  triggerClose() {
    this.onclose?.();
  }
}

function HookProbe({ onRender }: { onRender: (r: ReturnType<typeof useDashboardSocket>) => void }) {
  const result = useDashboardSocket();
  onRender(result);
  return null;
}

describe("useDashboardSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    // @ts-expect-error -- replacing the global WebSocket with a test double
    global.WebSocket = MockWebSocket;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("connects on mount and reflects connected=true on open", () => {
    let latest: ReturnType<typeof useDashboardSocket> | undefined;
    render(<HookProbe onRender={(r) => (latest = r)} />);

    expect(MockWebSocket.instances).toHaveLength(1);
    act(() => MockWebSocket.instances[0].triggerOpen());
    expect(latest?.connected).toBe(true);
  });

  it("exposes the latest parsed delta on message", () => {
    let latest: ReturnType<typeof useDashboardSocket> | undefined;
    render(<HookProbe onRender={(r) => (latest = r)} />);
    const socket = MockWebSocket.instances[0];
    act(() => socket.triggerOpen());

    const delta = {
      type: "dashboard.delta",
      scope: "card",
      event_id: "EVT1",
      payload: { status: "approved" },
      emitted_at: "2024-01-01T00:00:00Z",
    };
    act(() => socket.triggerMessage(delta));
    expect(latest?.lastDelta).toEqual(delta);
  });

  it("reconnects with backoff after the socket closes", async () => {
    render(<HookProbe onRender={() => {}} />);
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => MockWebSocket.instances[0].triggerClose());
    expect(MockWebSocket.instances).toHaveLength(1); // not yet retried

    act(() => vi.advanceTimersByTime(500));
    expect(MockWebSocket.instances).toHaveLength(2); // first retry after initial backoff

    act(() => MockWebSocket.instances[1].triggerClose());
    act(() => vi.advanceTimersByTime(500));
    expect(MockWebSocket.instances).toHaveLength(2); // backoff doubled, not yet due

    act(() => vi.advanceTimersByTime(500));
    expect(MockWebSocket.instances).toHaveLength(3); // second retry after doubled backoff
  });

  it("does not reconnect after the component unmounts", () => {
    const { unmount } = render(<HookProbe onRender={() => {}} />);
    const socket = MockWebSocket.instances[0];
    unmount();
    act(() => socket.triggerClose());
    act(() => vi.advanceTimersByTime(5000));
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
