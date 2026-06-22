// Minimal ambient types for the Mappls (MapMyIndia) Web JS SDK v3.0, loaded
// as a global script tag (https://sdk.mappls.com/map/sdk/web) rather than an
// npm module — the SDK attaches itself to `window.mappls`. It wraps
// MapLibre GL internally (confirmed via its own minified source), so the
// Map instance exposes real MapLibre methods like getLayer/removeLayer.

interface MapplsLngLat {
  lat: number;
  lng: number;
}

interface MapplsMapOptions {
  center?: MapplsLngLat;
  zoom?: number;
}

// Minimal MapLibre GL JS style-spec types needed for addLayer/addSource
// below — kept local rather than importing maplibre-gl's own types because
// this file declares global ambients (no module imports allowed) and only
// the `line` layer / `geojson` source shapes are actually used.
interface MapplsGeoJsonSourceSpec {
  type: "geojson";
  data: GeoJSON.FeatureCollection | GeoJSON.Feature;
}

interface MapplsStyleLayerSpec {
  id: string;
  type: "line" | "circle";
  source: string;
  paint?: Record<string, unknown>;
  layout?: Record<string, unknown>;
}

declare class MapplsMap {
  // Must be a container element *id string* — passing an HTMLElement
  // directly silently returns a non-functional instance (verified at
  // runtime: no map-specific methods on its prototype chain).
  constructor(containerId: string, options?: MapplsMapOptions);
  setCenter(position: MapplsLngLat): void;
  setZoom(zoom: number): void;
  getZoom(): number;
  panTo(position: MapplsLngLat): void;
  addListener(event: "load" | "click", handler: () => void): void;
  getLayer(id: string): unknown | undefined;
  removeLayer(id: string): void;
  // addLayer/addSource/removeSource are NOT Mappls-specific — this SDK
  // wraps MapLibre GL JS internally (the existing getLayer/removeLayer
  // above already prove that), so these are the real MapLibre GL JS Map
  // methods, signature-checked against node_modules/maplibre-gl's own
  // .d.ts. Unlike Marker/HeatmapLayer (Mappls-authored, runtime-verified
  // against the live SDK because their behaviour doesn't match their
  // docs), these are plain MapLibre — no Mappls quirks to verify.
  addSource(id: string, source: MapplsGeoJsonSourceSpec): void;
  removeSource(id: string): void;
  getSource(id: string): { setData(data: GeoJSON.FeatureCollection | GeoJSON.Feature): void } | undefined;
  addLayer(layer: MapplsStyleLayerSpec): void;
  setPaintProperty(layerId: string, name: string, value: unknown): void;
  remove(): void;
  resize(): void;
}

interface MapplsMarkerOptions {
  map: MapplsMap;
  position: MapplsLngLat;
  // Despite the name, this SDK's marker constructor never reads fillColor —
  // every marker renders the same fixed icon image regardless of this
  // option (verified at runtime against the SDK's own minified source).
  // Use `html` instead for any marker that needs to look different.
  fillColor?: string;
  // Raw HTML content for the marker element. When set, the SDK skips its
  // built-in icon image entirely and renders this markup instead — the only
  // documented way to give a marker a distinct appearance.
  html?: string;
  draggable?: boolean;
}

declare class MapplsMarker {
  constructor(options: MapplsMarkerOptions);
  // Verified at runtime: the underlying method is setLngLat({lat,lng}),
  // matching getLngLat()'s return shape — not setPosition as docs implied.
  setLngLat(position: MapplsLngLat): void;
  addListener(event: "click", handler: () => void): void;
  remove(): void;
}

interface MapplsInfoWindowOptions {
  map: MapplsMap;
  position: MapplsLngLat;
  content: string;
}

declare class MapplsInfoWindow {
  constructor(options: MapplsInfoWindowOptions);
  remove(): void;
}

interface MapplsHeatmapPoint {
  lng: number;
  lat: number;
  title?: string;
}

interface MapplsHeatmapOptions {
  map: MapplsMap;
  // Verified at runtime: passing a GeoJSON FeatureCollection object throws
  // ("geojson.indexOf is not a function") — the implementation only
  // supports a plain point array (or a ".geojson" URL string), and even
  // then hardcodes every point's weight to 10 internally. There is no
  // per-point weight option despite what the constructor name implies.
  data: MapplsHeatmapPoint[];
  radius?: number;
  opacity?: number;
  maxIntensity?: number;
  gradient?: string[];
  fitbounds?: boolean;
}

interface MapplsNamespace {
  Map: typeof MapplsMap;
  Marker: typeof MapplsMarker;
  InfoWindow: typeof MapplsInfoWindow;
  // Called as a plain function (`mappls.HeatmapLayer(...)`), never `new` —
  // the SDK's internal implementation reads `this` and breaks under `new`.
  HeatmapLayer(options: MapplsHeatmapOptions): { id: string; type: "heatmap" };
}

interface Window {
  mappls?: MapplsNamespace;
}
