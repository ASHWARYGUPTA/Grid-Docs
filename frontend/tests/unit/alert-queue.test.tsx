import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AlertQueue } from "@/app/live/_components/alert-queue";
import type { QueueItem } from "@/lib/types";

function makeItem(overrides: Partial<QueueItem>): QueueItem {
  return {
    event_id: "EVT1",
    card_id: null,
    rci: 0.5,
    p_closure: 0.3,
    severity_band: "Yellow",
    alert_priority: "MEDIUM",
    corridor: "Test Corridor",
    status: null,
    ...overrides,
  };
}

describe("AlertQueue", () => {
  it("renders rows in the order given by the backend (already RCI/priority sorted)", () => {
    const items = [
      makeItem({ event_id: "A", alert_priority: "CRITICAL", rci: 0.9, corridor: "Corridor A" }),
      makeItem({ event_id: "B", alert_priority: "HIGH", rci: 0.6, corridor: "Corridor B" }),
      makeItem({ event_id: "C", alert_priority: "LOW", rci: 0.1, corridor: "Corridor C" }),
    ];
    render(<AlertQueue items={items} selectedEventId={null} onSelect={() => {}} />);

    const rows = screen.getAllByRole("button").filter((el) => el.textContent?.includes("Corridor"));
    expect(rows[0]).toHaveTextContent("Corridor A");
    expect(rows[1]).toHaveTextContent("Corridor B");
    expect(rows[2]).toHaveTextContent("Corridor C");
  });

  it("shows an empty state when there are no active events", () => {
    render(<AlertQueue items={[]} selectedEventId={null} onSelect={() => {}} />);
    expect(screen.getByText("No active alerts")).toBeInTheDocument();
  });

  it("calls onSelect with the event_id when a row is clicked", () => {
    const onSelect = vi.fn();
    const items = [makeItem({ event_id: "EVT-CLICK", corridor: "Click Corridor" })];
    render(<AlertQueue items={items} selectedEventId={null} onSelect={onSelect} />);

    fireEvent.click(screen.getByText("Click Corridor"));
    expect(onSelect).toHaveBeenCalledWith("EVT-CLICK");
  });

  it("renders p_closure and rci formatted to 2 decimal places", () => {
    const items = [makeItem({ event_id: "EVT2", rci: 0.8874, p_closure: 0.123456 })];
    render(<AlertQueue items={items} selectedEventId={null} onSelect={() => {}} />);
    expect(screen.getByText("0.89")).toBeInTheDocument();
    expect(screen.getByText("0.12")).toBeInTheDocument();
  });
});
