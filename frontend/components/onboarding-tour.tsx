"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, X, LayoutGrid } from "lucide-react";
import { Button } from "@/components/ui/button";
import { isTourCompleted, markTourCompleted } from "@/lib/auth";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Tour step definitions
// ---------------------------------------------------------------------------

export interface TourStep {
  /** DOM element id to spotlight. Null = centre-screen (no spotlight). */
  targetId: string | null;
  /** Route to navigate to before showing this step. */
  route?: string;
  title: string;
  description: string;
  /** Tooltip placement relative to the target element. */
  placement?: "top" | "bottom" | "left" | "right";
  /** Optional callback to fire before spotlighting this step. */
  onEnter?: () => void;
}

const TOUR_STEPS: TourStep[] = [
  {
    targetId: null,
    title: "Welcome to Grid Unlocked",
    description:
      "This is the Command Dashboard — the real-time control centre for Bengaluru's traffic management. It pulls live data from sensors, AI dispatch engines, and field units. Let's walk through the key sections in under 2 minutes.",
  },
  {
    targetId: "tour-sidebar-nav",
    route: "/live",
    title: "Navigation sidebar",
    description:
      "Five sections: Live Monitor (real-time incidents), Planned Events (72h briefings), Governance (system health + tier control), Analytics (corridor forecasts), and Citizen Report (public submissions). Your role badge at the bottom shows what you can do.",
    placement: "right",
  },
  {
    targetId: "tour-alert-queue",
    route: "/live",
    title: "Alert queue",
    description:
      "Every active traffic incident appears here, ranked by severity × cascade risk. The AI computes a priority score every time a new event arrives. Click a row to open the dispatch card for that incident.",
    placement: "right",
  },
  {
    targetId: "tour-live-map",
    route: "/live",
    title: "Live map",
    description:
      "Hexagonal hotspot clusters show where congestion is concentrated right now. The selected incident's location is pinned. Brighter hexes = higher event density. Clusters update within seconds of a new ingest.",
    placement: "left",
  },
  {
    targetId: "tour-action-card",
    route: "/live",
    title: "Dispatch card (action card)",
    description:
      "When you select an incident the AI produces a recommendation: which unit to dispatch, predicted clearance time (ICT), P(closure), and a cascade risk score. Source is labelled MILP (optimal) or GREEDY_FALLBACK (used when the solver exceeded its 1.5s budget). Commanders approve or reject here.",
    placement: "left",
    onEnter: () => {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("tour-open-action-card"));
      }
    },
  },
  {
    targetId: "tour-planned-header",
    route: "/planned",
    title: "Planned events",
    description:
      "Known upcoming events (processions, VIP movements, construction) are ingested here up to 72 hours ahead. The AI generates a full briefing package: staffing numbers, barricade count, predicted closure probability, and recommended diversions — based on historical analogues of similar past events.",
    placement: "bottom",
  },
  {
    targetId: "tour-governance-tier",
    route: "/governance",
    title: "Governance & system tiers",
    description:
      "The system runs in one of three tiers. Tier 1 = everything healthy, full AI dispatch. Tier 2 = partial outage, switches to rule-based fallback. Tier 3 = major outage, manual SOP mode only. Transitions happen automatically; Admins can override manually. Shadow mode lets the AI make recommendations without acting on them — used to validate before going live.",
    placement: "bottom",
  },
  {
    targetId: "tour-governance-health",
    route: "/governance",
    title: "Module health",
    description:
      "Three critical systems keep this dashboard running: data ingestion (pulls in new incidents), the feature store (prepares data for the AI), and the impact engine (the ML model that scores risk). If data ingestion and the feature store both go down, the system drops to Tier 3 (manual mode). If only the impact engine goes down, it drops to Tier 2 and falls back to rule-based scoring instead of the ML model — this is NOT a critical failure.",
    placement: "right",
  },
  {
    targetId: "tour-analytics-header",
    route: "/analytics",
    title: "Analytics",
    description:
      "Corridor-level congestion forecasts from the Poisson GLM model, ranked by how much the current 4-hour window deviates from the historical baseline. 'At Risk' corridors are elevated by more than 15% above normal. CUSUM anomaly alerts appear when a corridor's event rate makes a structural shift.",
    placement: "bottom",
  },
  {
    targetId: null,
    title: "You're ready",
    description:
      "That's the full dashboard. Every section has an ⓘ button next to its title — click it any time to get a plain-English explanation of what you're looking at. You can replay this tour from the sidebar footer at any time.",
  },
];

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface TourContextValue {
  isActive: boolean;
  currentStep: number;
  totalSteps: number;
  step: TourStep | null;
  next: () => void;
  skip: () => void;
  startTour: () => void;
}

const TourContext = createContext<TourContextValue>({
  isActive: false,
  currentStep: 0,
  totalSteps: TOUR_STEPS.length,
  step: null,
  next: () => {},
  skip: () => {},
  startTour: () => {},
});

export function useTour() {
  return useContext(TourContext);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function TourProvider({
  userEmail,
  children,
}: {
  userEmail: string | null;
  children: React.ReactNode;
}) {
  const [isActive, setIsActive] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [spotlightRect, setSpotlightRect] = useState<DOMRect | null>(null);
  const router = useRouter();
  const navigatedRef = useRef(false);

  // Auto-start on first visit
  useEffect(() => {
    if (!userEmail) return;
    const timer = setTimeout(() => {
      if (!isTourCompleted(userEmail)) {
        setIsActive(true);
        setCurrentStep(0);
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [userEmail]);

  // Resolve spotlight whenever step or active state changes
  useEffect(() => {
    if (!isActive) return;
    const step = TOUR_STEPS[currentStep];

    const navigate = async () => {
      if (step.route && !navigatedRef.current) {
        navigatedRef.current = true;
        router.push(step.route);
        // Wait for navigation + render
        await new Promise((r) => setTimeout(r, 600));
      }
      navigatedRef.current = false;

      if (step.onEnter) {
        step.onEnter();
        // Give time for UI reactions like expanding a row
        await new Promise((r) => setTimeout(r, 300));
      }

      if (!step.targetId) {
        setSpotlightRect(null);
        return;
      }
      // Poll until element is mounted (up to 2s)
      let el: HTMLElement | null = null;
      for (let i = 0; i < 20; i++) {
        el = document.getElementById(step.targetId);
        if (el) break;
        await new Promise((r) => setTimeout(r, 100));
      }
      setSpotlightRect(el ? el.getBoundingClientRect() : null);
    };

    navigate();
  }, [isActive, currentStep, router]);

  const skip = useCallback(() => {
    setIsActive(false);
    if (userEmail) markTourCompleted(userEmail);
  }, [userEmail]);

  const next = useCallback(() => {
    if (currentStep >= TOUR_STEPS.length - 1) {
      skip();
      return;
    }
    setCurrentStep((s) => s + 1);
  }, [currentStep, skip]);

  const startTour = useCallback(() => {
    setCurrentStep(0);
    setIsActive(true);
  }, []);

  return (
    <TourContext.Provider
      value={{
        isActive,
        currentStep,
        totalSteps: TOUR_STEPS.length,
        step: isActive ? TOUR_STEPS[currentStep] : null,
        next,
        skip,
        startTour,
      }}
    >
      {children}
      {isActive && (
        <TourOverlay
          step={TOUR_STEPS[currentStep]}
          stepIndex={currentStep}
          totalSteps={TOUR_STEPS.length}
          spotlightRect={spotlightRect}
          onNext={next}
          onSkip={skip}
        />
      )}
    </TourContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Overlay renderer
// ---------------------------------------------------------------------------

const PAD = 8; // padding around spotlight element

function TourOverlay({
  step,
  stepIndex,
  totalSteps,
  spotlightRect,
  onNext,
  onSkip,
}: {
  step: TourStep;
  stepIndex: number;
  totalSteps: number;
  spotlightRect: DOMRect | null;
  onNext: () => void;
  onSkip: () => void;
}) {
  const isLast = stepIndex === totalSteps - 1;
  const isFirst = stepIndex === 0;

  // Tooltip positioning
  const tooltipStyle = useTooltipPosition(spotlightRect, step.placement ?? "bottom");

  return (
    <div className="fixed inset-0 z-[9999] pointer-events-none">
      {/* Dim backdrop with spotlight cutout */}
      {spotlightRect ? (
        <svg
          className="absolute inset-0 w-full h-full pointer-events-auto"
          style={{ cursor: "default" }}
          onClick={onNext}
        >
          <defs>
            <mask id="spotlight-mask">
              <rect width="100%" height="100%" fill="white" />
              <rect
                x={spotlightRect.left - PAD}
                y={spotlightRect.top - PAD}
                width={spotlightRect.width + PAD * 2}
                height={spotlightRect.height + PAD * 2}
                rx={6}
                fill="black"
              />
            </mask>
          </defs>
          <rect
            width="100%"
            height="100%"
            fill="rgba(0,0,0,0.55)"
            mask="url(#spotlight-mask)"
          />
          {/* Spotlight border */}
          <rect
            x={spotlightRect.left - PAD}
            y={spotlightRect.top - PAD}
            width={spotlightRect.width + PAD * 2}
            height={spotlightRect.height + PAD * 2}
            rx={6}
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            opacity={0.8}
          />
        </svg>
      ) : (
        <div
          className="absolute inset-0 bg-black/55 pointer-events-auto"
          onClick={isFirst || isLast ? undefined : onNext}
        />
      )}

      {/* Tooltip card */}
      <div
        className="absolute pointer-events-auto w-80 rounded-xl border border-border bg-background shadow-2xl"
        style={tooltipStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2 p-4 pb-2">
          <div className="flex items-center gap-2">
            <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground shrink-0">
              <LayoutGrid className="size-3.5" />
            </div>
            <p className="text-sm font-semibold leading-tight">{step.title}</p>
          </div>
          <button
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0 mt-0.5"
            onClick={onSkip}
            aria-label="Skip tour"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <p className="px-4 pb-4 text-xs text-muted-foreground leading-relaxed">
          {step.description}
        </p>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          {/* Progress dots */}
          <div className="flex items-center gap-1">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <div
                key={i}
                className={cn(
                  "rounded-full transition-all",
                  i === stepIndex
                    ? "w-4 h-1.5 bg-primary"
                    : "w-1.5 h-1.5 bg-muted-foreground/30"
                )}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {!isLast && (
              <button
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={onSkip}
              >
                Skip tour
              </button>
            )}
            <Button size="sm" className="h-7 text-xs gap-1.5" onClick={onNext}>
              {isLast ? "Finish" : "Next"}
              {!isLast && <ArrowRight className="size-3" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tooltip position hook — keeps the card on-screen
// ---------------------------------------------------------------------------

function useTooltipPosition(
  rect: DOMRect | null,
  placement: "top" | "bottom" | "left" | "right"
): React.CSSProperties {
  if (!rect) {
    // Centred on screen
    return {
      top: "50%",
      left: "50%",
      transform: "translate(-50%, -50%)",
    };
  }

  const CARD_W = 320;
  const CARD_H = 300; // approximate, increased to prevent clipping for long texts
  const GAP = 16;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1280;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;

  let top: number;
  let left: number;

  switch (placement) {
    case "right":
      top = rect.top + rect.height / 2 - CARD_H / 2;
      left = rect.right + GAP;
      break;
    case "left":
      top = rect.top + rect.height / 2 - CARD_H / 2;
      left = rect.left - CARD_W - GAP;
      break;
    case "top":
      top = rect.top - CARD_H - GAP;
      left = rect.left + rect.width / 2 - CARD_W / 2;
      break;
    default: // bottom
      top = rect.bottom + GAP;
      left = rect.left + rect.width / 2 - CARD_W / 2;
  }

  // Clamp to viewport
  left = Math.max(12, Math.min(left, vw - CARD_W - 12));
  top = Math.max(12, Math.min(top, vh - CARD_H - 12));

  return { top, left, position: "fixed" };
}
