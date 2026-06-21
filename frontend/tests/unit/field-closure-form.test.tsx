import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { ClosureForm, validateClosure } from "@/app/field/[recommendationId]/_components/closure-form";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { fieldClose: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

describe("validateClosure", () => {
  it("rejects negative barricades_used", () => {
    expect(validateClosure(-1, 1).valid).toBe(false);
    expect(validateClosure(-1, 1).barricadesError).toBeTruthy();
  });

  it("rejects officers_used below 1", () => {
    expect(validateClosure(0, 0).valid).toBe(false);
    expect(validateClosure(0, 0).officersError).toBeTruthy();
  });

  it("accepts valid bounds", () => {
    expect(validateClosure(0, 1).valid).toBe(true);
  });
});

describe("ClosureForm", () => {
  beforeEach(() => {
    vi.mocked(api.fieldClose).mockReset();
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("blocks submission and does not call the API when barricades_used is negative", async () => {
    render(<ClosureForm eventId="EVT1" alreadyClosed={false} onClosed={() => {}} />);

    fireEvent.change(screen.getByLabelText("Barricades used"), { target: { value: "-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Close event" }));

    await waitFor(() => expect(api.fieldClose).not.toHaveBeenCalled());
  });

  it("blocks submission when officers_used is 0", async () => {
    render(<ClosureForm eventId="EVT1" alreadyClosed={false} onClosed={() => {}} />);

    fireEvent.change(screen.getByLabelText("Officers used"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Close event" }));

    await waitFor(() => expect(api.fieldClose).not.toHaveBeenCalled());
  });

  it("submits with the expected request body on valid input", async () => {
    vi.mocked(api.fieldClose).mockResolvedValue({
      event_id: "EVT1",
      closure_id: "FCLOSE-1",
      event_closed: true,
      closed_datetime: "2024-01-01T00:00:00Z",
      queued_offline: false,
    });
    const onClosed = vi.fn();
    render(<ClosureForm eventId="EVT1" alreadyClosed={false} onClosed={onClosed} />);

    fireEvent.change(screen.getByLabelText("Barricades used"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Officers used"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Close event" }));

    await waitFor(() => expect(api.fieldClose).toHaveBeenCalledTimes(1));
    const [eventId, body] = vi.mocked(api.fieldClose).mock.calls[0];
    expect(eventId).toBe("EVT1");
    expect(body.barricades_used).toBe(3);
    expect(body.officers_used).toBe(2);
    expect(body.diversion_activated).toBe(true);
    await waitFor(() => expect(onClosed).toHaveBeenCalled());
  });

  it("shows the closed message instead of the form when alreadyClosed is true", () => {
    render(<ClosureForm eventId="EVT1" alreadyClosed={true} onClosed={() => {}} />);
    expect(screen.getByText("This event has already been closed.")).toBeInTheDocument();
  });
});
