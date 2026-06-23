"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bus,
  CalendarPlus,
  History,
  LayoutGrid,
  MapPin,
  MessageSquareWarning,
  Network,
  Radar,
  Route,
  Send,
  Shield,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AuroraBackground } from "@/components/landing/aurora-background";
import { useAuth } from "@/context/auth-context";
import { HowItWorks } from "./_components/how-it-works";

const CAPABILITIES = [
  {
    icon: Radar,
    title: "Real-time Hotspots",
    description: "Live density clustering surfaces emerging congestion as it forms.",
  },
  {
    icon: TrendingUp,
    title: "Predicted Hotspots",
    description: "Forecasts corridor-level risk hours ahead using historical patterns.",
  },
  {
    icon: MapPin,
    title: "Auto Station Assignment",
    description: "Matches the nearest capable unit to every incident automatically.",
  },
  {
    icon: Route,
    title: "Diversion Detection",
    description: "Suggests alternate routes the moment a corridor closure is likely.",
  },
  {
    icon: Sparkles,
    title: "AI Recommendations",
    description: "Calibrated, explainable action cards for every commander decision.",
  },
  {
    icon: MessageSquareWarning,
    title: "Citizen Reporting",
    description: "Photo + GPS reports from commuters feed straight into triage.",
  },
];

const DETAILED_FEATURES = [
  {
    id: "feature-1",
    title: "Live Incident Pins & RCI Mapping",
    subtitle: "Feature 1 — Real-time Incident Mapping",
    icon: MapPin,
    description:
      "Active traffic incidents from the ASTraM corpus are mapped in real time. Each incident is rendered as a map pin, color-coded dynamically by its Road Congestion Index (RCI) value to reflect congestion severity. Clicking a pin instantly loads its operational action card, providing an interactive, unified common operating picture.",
    specs: [
      "Endpoint: GET /api/v1/incidents/active",
      "Queue: Real-time list sorted by priority (e.g., CBD 1: RCI 0.98, CBD 2: RCI 0.97)",
      "Map Pins: Color-coded by RCI severity (Red, Orange, Yellow, Green) on MapMyIndia",
    ],
    image: "/live_monitor.png",
    caption: "Live monitor interface showing active incident pins, real-time alert queue with priorities and RCI scores, and map dashboard.",
  },
  {
    id: "feature-2",
    title: "Sub-Second WebSocket Incident Broadcast",
    subtitle: "Feature 2 — Real-time Ingestion Pipeline",
    icon: Radar,
    description:
      "Freshly ingested incidents are pushed directly from the ingestion bus to the client dashboard via WebSockets. High-RCI incidents automatically trigger a card preview, allowing traffic commanders to review and approve dispatches in under 1 second without manual polling.",
    specs: [
      "Protocol: WebSocket connection on /ws/dashboard",
      "Latency: Sub-second (< 1s) from ASTraM ingestion to UI",
      "Trigger: Automatically updates map pins and queue lists",
    ],
    image: "/action_card.png",
    caption: "Real-time dashboard updates reflecting new events instantly via WebSockets.",
  },
  {
    id: "feature-3",
    title: "Diversion Route Map Overlay",
    subtitle: "Feature 3 — Spatial Route Intelligence",
    icon: Route,
    description:
      "Commander-approved diversion scenarios are drawn directly onto the live map as ranked polylines. Node IDs from the backend proxy graph are resolved to real-world corridor coordinates. Hovering over a route in the action card's Routes tab dynamically highlights the corresponding polyline on the map, visualising alternative flows.",
    specs: [
      "Resolution: Node IDs mapped to real corridor centroids",
      "Layout: Rank-ordered line weights and highlight on hover",
      "Constraint: Skips drawing when coords are unresolved (no fabrication)",
    ],
    image: "/live_monitor.png",
    caption: "Diversion routes displayed as graded polylines on the MapMyIndia spatial map.",
  },
  {
    id: "feature-4",
    title: "De-hardcoded Planned Events & Predictive Impact",
    subtitle: "Feature 4 — Dynamic Location & ML Forecasting",
    icon: CalendarPlus,
    description:
      "Coordinate lookups for planned events are resolved dynamically using real corridor centroids fetched from the database, replacing the old static lookup. The operator interface features a search-input with datalist auto-suggest, live coordinate preview, and displays ML impact predictions (closure probability, incident clearance time, staffing) along with historical analogues.",
    specs: [
      "Centroid Lookup: Resolves Magadi Road to its database centroid (12.9851, 77.5233) dynamically",
      "ML Impact Prediction: Predicts 45% closure probability and 323.8h median clearance time",
      "Resource & Analogues: Suggests 4-12 officers (8 barricades) and lists past historical incidents",
    ],
    image: "/action_card.png",
    caption: "Planned event dialog resolving 'Magadi Road' with live ML impact predictions and analogues.",
  },
  {
    id: "feature-5",
    title: "Commander 'Close & Learn' Action",
    subtitle: "Feature 5 — Closed-Loop Learning",
    icon: History,
    description:
      "Commanders can close incidents directly from the live dashboard action card, entering real-world execution metrics. Submitting the closure feeds the event into the M13 replay buffer, which updates the ML models. The dashboard immediately displays retraining status, showing the feedback loop in action.",
    specs: [
      "Endpoint: POST /field/close/{event_id}",
      "Metrics: Barricades used, officers deployed, diversion activation status",
      "Learning Signal: Polls the latest retrain job and buffer sample count",
    ],
    image: "/close_learn_dialog.png",
    caption: "Close & Learn modal capturing operational metrics to retrain and update models.",
  },
  {
    id: "feature-6",
    title: "Cascade Propagation Overlay",
    subtitle: "Feature 6 — Network Risk Analytics",
    icon: Network,
    description:
      "Visualise cascade congestion risks on the live map as graded nodes and connecting edges. Risk levels are computed by the backend's GCDH (Graph-based Congestion Propagation) algorithm and mapped to real corridor centroids. Nodes are scaled and colored by risk, with edges tracing back to the seed incident.",
    specs: [
      "Endpoint: GET /propagation/active",
      "Visuals: Graded nodes (scaled by risk) and parent-to-child edges",
      "Controls: Easily toggled on/off in the map options",
    ],
    image: "/live_monitor.png",
    caption: "Cascade propagation layer mapping ripple effects and hops across the corridor network.",
  },
  {
    id: "feature-7",
    title: "Transit Impact Panel",
    subtitle: "Feature 7 — Public Transport Integration",
    icon: Bus,
    description:
      "Commanders can assess the impact of incidents on public transport via the Transit tab. This panel lazy-loads BMTC bus route information, predicted delays, occupancy, overload risk, passenger delay index, and advisory messages, allowing commanders to coordinate with transit authorities.",
    specs: [
      "Endpoint: GET /transit/impact/{event_id} (lazy-loaded on tab click)",
      "Metrics: Passenger Delay Index (PDI), Transfer Overload Risk",
      "Data: Occupancy, overlap fraction, and delay minutes per route",
    ],
    image: "/live_monitor_transit.png",
    caption: "Action card panel showing the Transit tab detailing affected BMTC bus routes.",
  },
  {
    id: "submodule-analytics-top",
    title: "Predictive Hotspots & Corridor Watchlist",
    subtitle: "Analytics — Spatial Risk Forecasting",
    icon: BarChart3,
    description:
      "The Hotspots Analytics page lists risk metrics and forecasts. The dashboard warns operators when corridors exceed threshold limits (e.g. 16 corridors above 15% threshold) and ranks them using Poisson forecast models over the next 4 hours.",
    specs: [
      "Congestion Warning: Active banner alerts when corridors cross the 15% congestion threshold",
      "Corridor Watch: Compares current rates vs. baseline (e.g. CBD 1: +1627.2% vs. baseline)",
      "Database Scale: Direct analysis of 8,170 historical events across all H3 cells",
    ],
    image: "/hotspots_analytics.png",
    caption: "Hotspots Analytics dashboard displaying the Corridor Watch list and risk metrics.",
  },
  {
    id: "submodule-analytics-detail",
    title: "CUSUM Anomaly Detection & Congestion Patterns",
    subtitle: "Analytics — Statistical Anomaly Tracking",
    icon: Activity,
    description:
      "Drill down into specific corridor anomalies using Cumulative Sum (CUSUM) statistical charts. View hourly congestion pattern distributions, total cell events, persistence levels, and local root causes (breakdowns, water logging, pot holes) to understand traffic patterns.",
    specs: [
      "CUSUM Detail: Identifies statistically unusual event rates (e.g. Magadi Road: 2.00/h vs baseline 0.07/h, 38.6 sigma)",
      "Hourly Pattern: Histograms showing distribution of events by hour of the day",
      "Root Cause Attribution: Ranks top local causes (e.g. vehicle breakdown: 257, water logging: 40)",
    ],
    image: "/hotspots_analytics_detail.png",
    caption: "Analytics detail view displaying CUSUM statistical tables and hourly cause patterns.",
  },
  {
    id: "submodule-governance",
    title: "Governance Console & Model Promotion",
    subtitle: "Governance — Platform Oversight",
    icon: Shield,
    description:
      "The Governance Console allows platform administrators to manage operational tiers, view module health rollups, and trigger cascade drills. It also handles model promotion, displaying checklist evaluations and allowing admins to promote newly trained models.",
    specs: [
      "Controls: Tier override, shadow mode toggle, cascade drill trigger",
      "Health: Real-time module status monitoring",
      "Promotion: Checklist validation and model version promotions",
    ],
    image: "/governance_console.png",
    caption: "Governance dashboard showing tier control, active drills, and model promotion checklist.",
  },
  {
    id: "submodule-citizen",
    title: "Citizen Reporting Interface",
    subtitle: "Citizen — Commuter Reporting Loop",
    icon: MessageSquareWarning,
    description:
      "Commuters can submit geolocated traffic reports including photo, cause, and GPS coordinates. The citizen reporting page tracks report status and lets commuters subscribe to specific corridors or H3 cell alerts, feeding reports directly into triage.",
    specs: [
      "Ingestion: Photo + location upload to citizen report service",
      "Verification: Admins verify report, automatically pushing it live",
      "Alerts: Commuters receive alerts for subscribed corridors",
    ],
    image: "/citizen_reporting.png",
    caption: "Citizen reporting portal and subscriptions page.",
  },
];

function HeroCta() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="h-9 w-40 rounded-lg bg-muted animate-pulse" />;
  }

  return (
    <Button
      size="lg"
      className="gap-1.5"
      nativeButton={false}
      render={<Link href={user ? "/live" : "/login"} />}
    >
      {user ? "Open dashboard" : "Sign in"}
      <ArrowRight className="size-4" />
    </Button>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto max-w-5xl px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <LayoutGrid className="size-4" />
            </div>
            <span className="font-semibold tracking-tight">Grid Unlocked</span>
          </div>
          <nav className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              nativeButton={false}
              render={<Link href="#features" />}
            >
              Features
            </Button>
            <Button
              variant="ghost"
              size="sm"
              nativeButton={false}
              render={<Link href="#how-it-works" />}
            >
              How it works
            </Button>
            <Button
              variant="outline"
              size="sm"
              nativeButton={false}
              render={<Link href="/login" />}
            >
              Sign in
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden border-b">
        <AuroraBackground />
        <div className="relative z-10 mx-auto max-w-5xl px-6 py-24 sm:py-32 text-center">
          <Badge variant="outline" className="mb-5 bg-background/50 backdrop-blur-sm">
            Intelligence layer for ASTraM
          </Badge>
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight">
            Grid Unlocked
          </h1>
          <p className="mt-5 max-w-2xl mx-auto text-lg text-muted-foreground leading-relaxed">
            Real-time hotspots, AI dispatch recommendations, and citizen reporting for Bengaluru
            Traffic Police — built on calibrated ML models trained on 8,173 real ASTraM incidents.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <HeroCta />
            <Button
              variant="outline"
              size="lg"
              nativeButton={false}
              render={<Link href="#features" />}
            >
              Explore features
            </Button>
          </div>
        </div>
      </section>

      {/* Capability summary strip */}
      <section className="py-16 bg-muted/10 border-b">
        <div className="mx-auto max-w-5xl px-6">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold">Key System Capabilities</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Advanced spatial and predictive intelligence for modern urban traffic control.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {CAPABILITIES.map(({ icon: Icon, title, description }) => (
              <Card key={title}>
                <CardHeader className="pb-2">
                  <div className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary mb-2">
                    <Icon className="size-4" />
                  </div>
                  <CardTitle className="text-base">{title}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">{description}</CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Detailed Features Section */}
      <section id="features" className="py-20 border-b">
        <div className="mx-auto max-w-5xl px-6">
          <div className="text-center mb-16">
            <Badge className="mb-3">Detailed Feature Specifications</Badge>
            <h2 className="text-3xl font-bold tracking-tight">Core System Features</h2>
            <p className="text-muted-foreground mt-3 max-w-2xl mx-auto">
              Explore the detailed technical specifications and operational views of the Grid Unlocked ecosystem.
            </p>
          </div>

          <div className="space-y-24">
            {DETAILED_FEATURES.map((feat, idx) => {
              const Icon = feat.icon;
              const isEven = idx % 2 === 0;
              return (
                <div
                  key={feat.id}
                  className={`flex flex-col lg:flex-row items-center gap-10 lg:gap-16 ${
                    isEven ? "" : "lg:flex-row-reverse"
                  }`}
                >
                  {/* Feature Text */}
                  <div className="flex-1 space-y-4">
                    <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                      {feat.subtitle}
                    </span>
                    <div className="flex items-center gap-2">
                      <div className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary">
                        <Icon className="size-4" />
                      </div>
                      <h3 className="text-xl font-bold tracking-tight">{feat.title}</h3>
                    </div>
                    <p className="text-muted-foreground leading-relaxed text-sm">
                      {feat.description}
                    </p>
                    <Separator className="my-2" />
                    <ul className="space-y-1.5">
                      {feat.specs.map((spec, sidx) => (
                        <li key={sidx} className="flex items-start gap-2 text-xs">
                          <Activity className="size-3.5 text-primary shrink-0 mt-0.5" />
                          <span className="text-muted-foreground font-mono">{spec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Feature Image */}
                  <div className="flex-1 w-full">
                    <div className="overflow-hidden rounded-xl border bg-card/65 shadow-md hover:shadow-lg transition-all duration-300">
                      <img
                        src={feat.image}
                        alt={feat.title}
                        className="w-full h-auto object-cover border-b"
                      />
                      <div className="p-3 bg-muted/20 text-[11px] text-muted-foreground italic flex items-center gap-1.5">
                        <Sparkles className="size-3.5 text-primary shrink-0" />
                        {feat.caption}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* How it works section (Preserved) */}
      <HowItWorks />

      {/* Footer */}
      <footer className="border-t py-10 bg-muted/5">
        <div className="mx-auto max-w-5xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <LayoutGrid className="size-4" />
            <span>Grid Unlocked — all 18 planned modules implemented</span>
          </div>
          <div className="flex items-center gap-4">
            <Button
              variant="link"
              size="sm"
              className="text-muted-foreground"
              nativeButton={false}
              render={<Link href="/login" />}
            >
              Sign in
              <Send className="size-3.5" />
            </Button>
          </div>
        </div>
        <Separator className="mt-8 mb-4 mx-auto max-w-5xl" />
        <p className="text-center text-xs text-muted-foreground">
          An intelligence layer for ASTraM — not a replacement.
        </p>
      </footer>
    </div>
  );
}

