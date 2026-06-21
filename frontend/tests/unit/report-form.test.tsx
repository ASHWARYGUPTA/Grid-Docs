import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { ReportForm, canSubmitReport } from "@/app/report/_components/report-form";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { citizenReport: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

describe("canSubmitReport", () => {
  it("requires a photo or a location, not both", () => {
    expect(canSubmitReport(false, false)).toBe(false);
    expect(canSubmitReport(true, false)).toBe(true);
    expect(canSubmitReport(false, true)).toBe(true);
    expect(canSubmitReport(true, true)).toBe(true);
  });
});

function makePhotoFile(): File {
  return new File(["fake-bytes"], "photo.jpg", { type: "image/jpeg" });
}

describe("ReportForm", () => {
  beforeEach(() => {
    vi.mocked(api.citizenReport).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("does not call the API when there is no photo and no location", async () => {
    render(<ReportForm onSubmitted={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Submit report" }));
    await waitFor(() => expect(api.citizenReport).not.toHaveBeenCalled());
  });

  it("submits with a photo and includes lat/lon when geolocation succeeds", async () => {
    const getCurrentPosition = vi.fn((success: PositionCallback) => {
      success({
        coords: { latitude: 12.97, longitude: 77.59 },
      } as GeolocationPosition);
    });
    Object.defineProperty(global.navigator, "geolocation", {
      value: { getCurrentPosition },
      configurable: true,
    });

    vi.mocked(api.citizenReport).mockResolvedValue({
      report_id: "CTZ-1",
      status: "pending",
      h3_cell: "872a1072",
      corridor: "Mysore Road",
      junction: null,
      ict_p50: 1.2,
      ict_p80: 2.1,
      p_closure: 0.1,
      cause_hint: "accident",
      cause_confidence: 0.65,
      event_id: "EVT-1",
      has_photo: true,
      created_at: "2024-01-01T00:00:00Z",
    });

    const onSubmitted = vi.fn();
    render(<ReportForm onSubmitted={onSubmitted} />);

    const fileInput = screen.getByLabelText("Photo") as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [makePhotoFile()] } });

    fireEvent.click(screen.getByRole("button", { name: "Share my location" }));
    await waitFor(() => expect(getCurrentPosition).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Submit report" }));

    await waitFor(() => expect(api.citizenReport).toHaveBeenCalledTimes(1));
    const [formData] = vi.mocked(api.citizenReport).mock.calls[0];
    expect(formData.get("lat")).toBe("12.97");
    expect(formData.get("lon")).toBe("77.59");
    expect(formData.get("photo")).toBeInstanceOf(File);
    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
  });

  it("submits with just a photo when geolocation is denied", async () => {
    const getCurrentPosition = vi.fn((_success: PositionCallback, error?: PositionErrorCallback) => {
      error?.({} as GeolocationPositionError);
    });
    Object.defineProperty(global.navigator, "geolocation", {
      value: { getCurrentPosition },
      configurable: true,
    });

    vi.mocked(api.citizenReport).mockResolvedValue({
      report_id: "CTZ-2",
      status: "pending",
      h3_cell: "872a1072",
      corridor: null,
      junction: null,
      ict_p50: 1.0,
      ict_p80: 1.6,
      p_closure: 0.08,
      cause_hint: "unknown_obstruction",
      cause_confidence: 0.2,
      event_id: null,
      has_photo: true,
      created_at: "2024-01-01T00:00:00Z",
    });

    render(<ReportForm onSubmitted={() => {}} />);

    const fileInput = screen.getByLabelText("Photo") as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [makePhotoFile()] } });

    fireEvent.click(screen.getByRole("button", { name: "Submit report" }));

    await waitFor(() => expect(api.citizenReport).toHaveBeenCalledTimes(1));
    const [formData] = vi.mocked(api.citizenReport).mock.calls[0];
    expect(formData.get("lat")).toBeNull();
    expect(formData.get("lon")).toBeNull();
  });
});
