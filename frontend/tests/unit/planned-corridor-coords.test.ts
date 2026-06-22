import { describe, expect, it } from "vitest";
import { resolveCorridorCoords } from "@/app/planned/page";
import type { CorridorCentroid } from "@/lib/types";

// Planned-event ingest coordinates must come from the real corridor_centroids
// (GET /api/v1/corridors), never a hardcoded lookup. City centre is the fallback.
const CITY_CENTRE: [number, number] = [12.9716, 77.5946];

const CENTROIDS: CorridorCentroid[] = [
  { name: "Mysore Road", lat: 12.9535, lon: 77.5229, sample_count: 120 },
  { name: "Tumkur Road", lat: 13.0281, lon: 77.5367, sample_count: 88 },
];

describe("resolveCorridorCoords", () => {
  it("returns the real centroid on an exact name match", () => {
    expect(resolveCorridorCoords("Mysore Road", CENTROIDS)).toEqual([12.9535, 77.5229]);
  });

  it("matches case-insensitively", () => {
    expect(resolveCorridorCoords("mysore road", CENTROIDS)).toEqual([12.9535, 77.5229]);
  });

  it("matches a partial corridor name fuzzily", () => {
    // "Mysore" is contained in "Mysore Road"
    expect(resolveCorridorCoords("Mysore", CENTROIDS)).toEqual([12.9535, 77.5229]);
  });

  it("falls back to the city centre for an unknown corridor", () => {
    expect(resolveCorridorCoords("Nonexistent Avenue", CENTROIDS)).toEqual(CITY_CENTRE);
  });

  it("falls back to the city centre for null / empty input", () => {
    expect(resolveCorridorCoords(null, CENTROIDS)).toEqual(CITY_CENTRE);
    expect(resolveCorridorCoords("   ", CENTROIDS)).toEqual(CITY_CENTRE);
  });

  it("falls back to the city centre when no centroids are loaded yet", () => {
    expect(resolveCorridorCoords("Mysore Road", [])).toEqual(CITY_CENTRE);
  });
});
