"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";
import * as h3 from "h3-js";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useDashboardSocket } from "@/lib/ws";
import type { ActionCard, CellDensityPoint, HotspotCluster } from "@/lib/types";

const BENGALURU_CENTER: MapplsLngLat = { lat: 12.9716, lng: 77.5946 };
const MAP_CONTAINER_ID = "mappls-live-map";

const MAPPLS_KEY = process.env.NEXT_PUBLIC_MAPPLS_KEY;
const MAPPLS_SDK_URL = `https://sdk.mappls.com/map/sdk/web?v=3.0&access_token=${MAPPLS_KEY}`;

const HEATMAP_GRADIENT = ["#22c55e", "#facc15", "#f97316", "#dc2626"];

// Distinct from the heatmap palette — used only for the marker placed by a
// click-to-locate action, so it's visually obvious which pin the zoom
// animation just flew to.
const HIGHLIGHT_COLOR = "#9333ea";

// The SDK's `fillColor` marker option is a no-op (verified against its own
// minified source: createMarkerElement always paints a fixed icon image
// unless given raw `html`, which it renders in place of that image
// instead) — so the highlight pin is built by hand as inline SVG. The
// outer circle uses a CSS animation (defined globally below) for a pulse
// ring that draws the eye to the marker right as the fly-to animation
// settles.
const HIGHLIGHT_MARKER_HTML = `
  <div style="position:relative;width:34px;height:48px">
    <span style="position:absolute;left:7px;top:21px;width:20px;height:20px;border-radius:50%;background:${HIGHLIGHT_COLOR};opacity:0.35;animation:grid-unlocked-pin-pulse 1.2s ease-out infinite"></span>
    <svg width="34" height="48" viewBox="0 0 34 48" style="position:absolute;left:0;top:0">
      <path d="M17 0C7.6 0 0 7.6 0 17c0 12.4 17 31 17 31s17-18.6 17-31C34 7.6 26.4 0 17 0z" fill="${HIGHLIGHT_COLOR}" stroke="#fff" stroke-width="1.5" />
      <circle cx="17" cy="17" r="6" fill="#fff" />
    </svg>
  </div>`;

// Mappls's typed API only exposes instant setZoom/panTo (no flyTo/easeTo),
// so the "zoom out then in" effect is staged by hand: zoom out from
// wherever the map currently is, pan while zoomed out, then step the zoom
// back in. setTimeout (not an interval) is used per-step since each step's
// delay is intentionally non-uniform (pause longer at the zoomed-out apex
// so the viewport change is perceptible before zooming back in).
const ZOOM_OUT_STEP = 3;
const ZOOM_OUT_MIN = 9;
const ZOOM_STEP_MS = 220;

// mappls.HeatmapLayer's point-array input path hardcodes every point's
// weight to 10 (verified in its source — there is no per-point weight
// option), and its only other input path requires a literal ".geojson"
// URL string or array (calls `.indexOf` on whatever is passed, which
// throws on a plain FeatureCollection object). So density is simulated by
// repeating each cell's centroid proportionally to its event count —
// MapLibre's heatmap renderer accumulates overlapping points into a
// stronger signal, producing the same visual effect as a real weight.
//
// This uses /hotspots/density (full historical per-cell counts, ~150 days
// of real ASTraM data) rather than /hotspots/observed (live, last-24h-only,
// which is correctly sparse in a fresh demo and would otherwise render as
// a handful of isolated dots instead of the broad gradient field a
// city-wide congestion heatmap is supposed to show).
function densityToHeatmapPoints(cells: CellDensityPoint[]): MapplsHeatmapPoint[] {
  const maxCount = Math.max(...cells.map((c) => c.count), 1);
  const points: MapplsHeatmapPoint[] = [];
  for (const cell of cells) {
    // Scale into a bounded repeat range so one extreme outlier cell can't
    // make every other cell's signal disappear by comparison.
    const repeats = Math.max(1, Math.round((cell.count / maxCount) * 40));
    for (let i = 0; i < repeats; i++) {
      points.push({ lat: cell.centroid_lat, lng: cell.centroid_lon, title: cell.h3_res7 });
    }
  }
  return points;
}

function hourlyHistogramSvg(hourlyCounts: number[]): string {
  const width = 220;
  const height = 70;
  const barGap = 1;
  const barWidth = width / hourlyCounts.length - barGap;
  const max = Math.max(...hourlyCounts, 1);
  const bars = hourlyCounts
    .map((count, hour) => {
      const barHeight = (count / max) * (height - 12);
      const x = hour * (barWidth + barGap);
      const y = height - barHeight - 12;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" fill="#dc2626" />`;
    })
    .join("");
  return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${bars}<text x="0" y="${height}" font-size="9" fill="#666">0h</text><text x="${width - 22}" y="${height}" font-size="9" fill="#666">23h</text></svg>`;
}

function buildCellPopupHtml(summary: {
  total_events: number;
  top_causes: { cause: string }[];
  top_corridors: { corridor: string }[];
  hourly_counts: number[];
}): string {
  const topCause = summary.top_causes[0]?.cause ?? "unknown";
  const topCorridor = summary.top_corridors[0]?.corridor ?? "Non-corridor";
  return `
    <div style="font-size:12px;min-width:230px">
      <div style="font-weight:600;margin-bottom:2px">${topCorridor}</div>
      <div style="color:#666;margin-bottom:6px">${summary.total_events} events &middot; top cause: ${topCause}</div>
      ${hourlyHistogramSvg(summary.hourly_counts)}
      <div style="color:#999;margin-top:2px">events by hour of day (IST)</div>
    </div>`;
}

interface MapPanelProps {
  selectedCard: ActionCard | null;
}

export function MapPanel({ selectedCard }: MapPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapplsMap | null>(null);
  const [sdkReady, setSdkReady] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);
  const heatmapLayerIdRef = useRef<string | null>(null);
  const clusterMarkersRef = useRef<MapplsMarker[]>([]);
  const selectedMarkerRef = useRef<MapplsMarker | null>(null);
  const predictedMarkerRef = useRef<MapplsMarker | null>(null);
  // Pending steps of an in-flight zoom-out/zoom-in animation — cleared and
  // replaced whenever a new target is selected before the previous
  // animation finishes, so two quick clicks don't fight over the viewport.
  const zoomAnimationTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  // Guards against overlapping refreshObserved() calls (a hotspot delta can
  // arrive mid-fetch from an earlier visibility-toggle refresh) clobbering
  // each other's marker/layer state out of order.
  const refreshGenerationRef = useRef(0);
  const [showObserved, setShowObserved] = useState(true);
  const [showPredicted, setShowPredicted] = useState(false);
  const [sdkLoadFailed, setSdkLoadFailed] = useState(false);
  const { lastDelta } = useDashboardSocket();

  useEffect(() => {
    if (!sdkReady || !containerRef.current || mapRef.current || !window.mappls) return;
    // Mappls's Map constructor only initializes correctly given a container
    // *id string* — passing the element directly silently returns a
    // near-empty, non-functional instance with no map-specific methods.
    const map = new window.mappls.Map(MAP_CONTAINER_ID, {
      center: BENGALURU_CENTER,
      zoom: 11,
    });
    mapRef.current = map;
    map.addListener("load", () => setMapLoaded(true));

    const resizeObserver = new ResizeObserver(() => {
      map.resize();
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      zoomAnimationTimersRef.current.forEach(clearTimeout);
      zoomAnimationTimersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, [sdkReady]);

  function refreshObserved(map: MapplsMap) {
    // The heatmap intensity field is the rich, full-history per-cell
    // density (so the map always shows a real, broad gradient rather than
    // a handful of dots from whatever happens to be live right now);
    // click-to-histogram markers are placed on the same dense cells, not
    // just the sparse live-observed clusters, so most of the visible
    // heatmap is actually clickable.
    const generation = ++refreshGenerationRef.current;
    Promise.all([api.hotspotsDensity(2), api.hotspotsObserved()])
      .then(([density, observed]) => {
        // A newer refreshObserved() call already won — discard this
        // stale response instead of clobbering its markers/layer.
        if (generation !== refreshGenerationRef.current) return;
        if (!window.mappls) return;
        if (heatmapLayerIdRef.current && map.getLayer(heatmapLayerIdRef.current)) {
          map.removeLayer(heatmapLayerIdRef.current);
        }
        clusterMarkersRef.current.forEach((m) => m.remove());
        clusterMarkersRef.current = [];

        // Called as a plain function, not `new` — this SDK's heatmap/geojson
        // helpers read `this` internally and break when constructed.
        const layer = window.mappls.HeatmapLayer({
          map,
          data: densityToHeatmapPoints(density.cells),
          radius: 35,
          opacity: 0.8,
          maxIntensity: 1,
          gradient: HEATMAP_GRADIENT,
        });
        heatmapLayerIdRef.current = layer.id;

        // The heatmap layer has no per-feature click handling, so an
        // invisible marker per dense cell carries the click-to-histogram
        // interaction. Capped to the top-N densest cells — one marker per
        // historical cell (often 100+) would visibly slow marker churn on
        // every refresh and isn't needed for the interaction to feel
        // complete, since the densest cells are exactly what a user is
        // most likely to click on.
        const topCells = [...density.cells].sort((a, b) => b.count - a.count).slice(0, 30);
        clusterMarkersRef.current = topCells.map((cell) => {
          const marker = new window.mappls!.Marker({
            map,
            position: { lat: cell.centroid_lat, lng: cell.centroid_lon },
            fillColor: "transparent",
          });
          marker.addListener("click", () => showCellHistogramPopup(map, cell.h3_res7, cell.centroid_lat, cell.centroid_lon));
          return marker;
        });

        // Live-observed clusters (last 24h / active) still get their own
        // markers even if not in the top-30 densest, since those are the
        // operationally relevant ones right now.
        for (const cluster of observed.clusters) {
          const cell = cluster.h3_cells[0];
          if (!cell || topCells.some((c) => c.h3_res7 === cell)) continue;
          const marker = new window.mappls!.Marker({
            map,
            position: { lat: cluster.centroid_lat, lng: cluster.centroid_lon },
            fillColor: "transparent",
          });
          marker.addListener("click", () => showCellHistogramPopup(map, cell, cluster.centroid_lat, cluster.centroid_lon));
          clusterMarkersRef.current.push(marker);
        }
      })
      .catch((err) => {
        // Swallow so a transient backend/SDK failure doesn't crash the
        // whole live page, but keep the error visible for debugging
        // rather than failing completely silently.
        console.error("MapPanel: failed to refresh hotspot layer", err);
      });
  }

  // Zooms out from the current viewport, pans to the target while zoomed
  // out, then zooms back in — giving a visible "fly across the map" effect
  // instead of an instant jump cut to the new location.
  function flyToWithZoomAnimation(map: MapplsMap, target: MapplsLngLat, targetZoom: number) {
    zoomAnimationTimersRef.current.forEach(clearTimeout);
    zoomAnimationTimersRef.current = [];

    const startZoom = map.getZoom();
    const outZoom = Math.max(ZOOM_OUT_MIN, startZoom - ZOOM_OUT_STEP);

    map.setZoom(outZoom);
    zoomAnimationTimersRef.current.push(
      setTimeout(() => {
        map.panTo(target);
        zoomAnimationTimersRef.current.push(
          setTimeout(() => {
            map.setZoom(targetZoom);
          }, ZOOM_STEP_MS),
        );
      }, ZOOM_STEP_MS),
    );
  }

  function showCellHistogramPopup(map: MapplsMap, cell: string, lat: number, lng: number) {
    api
      .hotspotsCell(cell)
      .then((summary) => {
        if (!window.mappls) return;
        try {
          new window.mappls.InfoWindow({ map, position: { lat, lng }, content: buildCellPopupHtml(summary) });
        } catch {
          // Swallow — a failed popup shouldn't take down the rest of the map.
        }
      })
      .catch(() => {});
  }

  // No documented hide/show toggle for a heatmap layer or marker in this
  // SDK, so visibility is implemented as remove-on-hide / refetch-on-show.
  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !map || !window.mappls) return;
    if (showObserved) {
      refreshObserved(map);
      return;
    }
    if (heatmapLayerIdRef.current && map.getLayer(heatmapLayerIdRef.current)) {
      map.removeLayer(heatmapLayerIdRef.current);
      heatmapLayerIdRef.current = null;
    }
    clusterMarkersRef.current.forEach((m) => m.remove());
    clusterMarkersRef.current = [];
  }, [showObserved, mapLoaded]);

  // Refresh observed hotspots whenever a hotspot delta arrives.
  useEffect(() => {
    if (lastDelta?.scope === "hotspot" && mapRef.current) {
      refreshObserved(mapRef.current);
    }
  }, [lastDelta]);

  // Move the single selected-event marker to the card's location, derived
  // from impact context — reuses one marker instance via setPosition rather
  // than removing/recreating, since marker removal isn't documented here.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.mappls) return;
    if (!selectedCard?.hotspot_context.h3_res7) {
      selectedMarkerRef.current?.remove();
      selectedMarkerRef.current = null;
      return;
    }

    let lat: number, lng: number;
    try {
      [lat, lng] = h3.cellToLatLng(selectedCard.hotspot_context.h3_res7);
    } catch {
      // Malformed h3 cell from the backend — no usable location, leave the
      // map as-is rather than throwing and breaking the whole panel.
      return;
    }
    if (selectedMarkerRef.current) {
      selectedMarkerRef.current.setLngLat({ lat, lng });
    } else {
      selectedMarkerRef.current = new window.mappls.Marker({
        map,
        position: { lat, lng },
        html: HIGHLIGHT_MARKER_HTML,
      });
    }
    flyToWithZoomAnimation(map, { lat, lng }, 13);
  }, [selectedCard]);

  function flyToPredictedCorridor(lat: number, lng: number) {
    const map = mapRef.current;
    if (!map || !window.mappls) return;
    if (predictedMarkerRef.current) {
      predictedMarkerRef.current.setLngLat({ lat, lng });
    } else {
      predictedMarkerRef.current = new window.mappls.Marker({
        map,
        position: { lat, lng },
        html: HIGHLIGHT_MARKER_HTML,
      });
    }
    flyToWithZoomAnimation(map, { lat, lng }, 13);
  }

  if (!MAPPLS_KEY) {
    return (
      <div className="h-full w-full flex items-center justify-center text-sm text-muted-foreground bg-muted/30 p-4 text-center">
        Map unavailable — NEXT_PUBLIC_MAPPLS_KEY is not configured.
      </div>
    );
  }

  if (sdkLoadFailed) {
    return (
      <div className="h-full w-full flex items-center justify-center text-sm text-muted-foreground bg-muted/30 p-4 text-center">
        Map failed to load. Check your network connection and reload the page.
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <style>{`
        @keyframes grid-unlocked-pin-pulse {
          0% { transform: scale(1); opacity: 0.35; }
          100% { transform: scale(2.6); opacity: 0; }
        }
      `}</style>
      <Script
        src={MAPPLS_SDK_URL}
        strategy="afterInteractive"
        onReady={() => setSdkReady(true)}
        onError={() => setSdkLoadFailed(true)}
      />
      <div ref={containerRef} id={MAP_CONTAINER_ID} className="h-full w-full" />
      <div className="absolute top-2 left-2 flex gap-1 bg-background/90 rounded-md p-1 border">
        <Button
          size="sm"
          variant={showObserved ? "default" : "outline"}
          onClick={() => setShowObserved((v) => !v)}
        >
          Observed
        </Button>
        <Button
          size="sm"
          variant={showPredicted ? "default" : "outline"}
          onClick={() => setShowPredicted((v) => !v)}
        >
          Predicted
        </Button>
      </div>
      {showPredicted && <PredictedForecastList onSelect={flyToPredictedCorridor} />}
    </div>
  );
}

function PredictedForecastList({
  onSelect,
}: {
  onSelect: (lat: number, lng: number) => void;
}) {
  const [forecasts, setForecasts] = useState<
    { corridor: string; lift_pct: number; expected_count: number; centroid_lat: number | null; centroid_lon: number | null }[]
  >([]);

  useEffect(() => {
    api
      .hotspotsPredicted()
      .then((res) => setForecasts(res.forecasts))
      .catch(() => {});
  }, []);

  return (
    <div className="absolute bottom-2 left-2 right-2 bg-background/95 border rounded-md p-2 max-h-32 overflow-y-auto text-xs">
      <p className="font-medium mb-1">Predicted corridor lift (next horizon)</p>
      {forecasts.length === 0 && <p className="text-muted-foreground">No forecast data</p>}
      {forecasts.map((f) => {
        const hasLocation = f.centroid_lat !== null && f.centroid_lon !== null;
        return (
          <div
            key={f.corridor}
            className={`flex justify-between ${hasLocation ? "cursor-pointer hover:bg-muted rounded-sm" : ""}`}
            onClick={() => hasLocation && onSelect(f.centroid_lat!, f.centroid_lon!)}
          >
            <span>{f.corridor}</span>
            <span className={f.lift_pct > 0 ? "text-destructive" : "text-muted-foreground"}>
              {f.lift_pct > 0 ? "+" : ""}
              {f.lift_pct.toFixed(0)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
