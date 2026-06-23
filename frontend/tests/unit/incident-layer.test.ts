import { describe, expect, it } from "vitest";
import { rciColor } from "@/app/live/_components/map-panel";

// rciColor drives the colour of every live incident pin on the map — these
// thresholds must agree with the bands documented in the build guide
// (red >0.7, orange 0.4-0.7, yellow 0.2-0.4, green <0.2) and with the
// border colours ActionCardPanel already uses for the same RCI value, so a
// pin's colour never disagrees with the card it opens.
describe("rciColor", () => {
  it("returns neutral grey when the incident has not been scored yet", () => {
    expect(rciColor(null)).toBe("#9ca3af");
  });

  it("returns red for rci > 0.7", () => {
    expect(rciColor(0.71)).toBe("#dc2626");
    expect(rciColor(1)).toBe("#dc2626");
  });

  it("returns orange for rci in (0.4, 0.7]", () => {
    expect(rciColor(0.7)).toBe("#f97316");
    expect(rciColor(0.41)).toBe("#f97316");
  });

  it("returns yellow for rci in (0.2, 0.4]", () => {
    expect(rciColor(0.4)).toBe("#facc15");
    expect(rciColor(0.21)).toBe("#facc15");
  });

  it("returns green for rci <= 0.2", () => {
    expect(rciColor(0.2)).toBe("#22c55e");
    expect(rciColor(0)).toBe("#22c55e");
  });
});
