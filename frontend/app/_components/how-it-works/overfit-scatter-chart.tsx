"use client";

import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { OVERFIT_ROWS, type OverfitRow } from "./data";

const FAMILY_CONFIG: ChartConfig = {
  baseline: { label: "Baseline", color: "var(--muted-foreground)" },
  linear: { label: "Linear", color: "var(--chart-2)" },
  forest: { label: "Forest", color: "var(--chart-3)" },
  gbdt: { label: "Gradient boosting", color: "var(--chart-1)" },
  resample: { label: "Resampling + GBDT", color: "var(--chart-4)" },
  deep: { label: "Deep learning", color: "var(--chart-5)" },
  ensemble: { label: "Stacking", color: "var(--chart-1)" },
  foundation: { label: "Foundation model", color: "var(--chart-5)" },
};

const FAMILY_ORDER = Object.keys(FAMILY_CONFIG) as Array<keyof typeof FAMILY_CONFIG>;

// Only rows with both a train and CV score can be plotted on this axis pair —
// the handful of deep-learning arms (TabNet/MLP/FT-Transformer) didn't have a
// CV loop wired in the notebook and are omitted here, not hidden elsewhere.
const PLOTTABLE = OVERFIT_ROWS.filter(
  (r): r is OverfitRow & { trainPrAuc: number; cvPrAuc: number } =>
    r.trainPrAuc != null && r.cvPrAuc != null
);

export function OverfitScatterChart() {
  return (
    <ChartContainer config={FAMILY_CONFIG} className="aspect-auto h-85 w-full">
      <ScatterChart margin={{ top: 16, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="trainPrAuc"
          name="Train PR-AUC"
          domain={[0, 1]}
          tickFormatter={(v) => v.toFixed(1)}
          label={{ value: "Train PR-AUC", position: "insideBottom", offset: -4, fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="cvPrAuc"
          name="CV PR-AUC"
          domain={[0, 0.45]}
          tickFormatter={(v) => v.toFixed(2)}
          label={{ value: "CV PR-AUC", angle: -90, position: "insideLeft", fontSize: 12 }}
        />
        <ZAxis range={[60, 60]} />
        <ReferenceLine
          segment={[
            { x: 0, y: 0 },
            { x: 1, y: 1 },
          ]}
          stroke="var(--border)"
          strokeDasharray="4 4"
          ifOverflow="extendDomain"
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              labelFormatter={(_, payload) => {
                const item = payload?.[0]?.payload;
                if (!item) return null;
                return (
                  <div className="flex flex-col gap-0.5 mb-1.5">
                    <span className="font-semibold text-foreground">{item.model}</span>
                    <span className="text-[10px] text-muted-foreground font-normal">{item.method}</span>
                  </div>
                );
              }}
              formatter={(value, name) => [
                typeof value === "number" ? value.toFixed(3) : value,
                name,
              ]}
            />
          }
        />
        {FAMILY_ORDER.map((family) => {
          const rows = PLOTTABLE.filter((r) => r.family === family);
          if (rows.length === 0) return null;
          return (
            <Scatter key={family} name={String(FAMILY_CONFIG[family].label)} data={rows} fill={`var(--color-${family})`}>
              {rows.map((row) => (
                <Cell key={`${row.model}-${row.method}`} fill={`var(--color-${family})`} />
              ))}
            </Scatter>
          );
        })}
      </ScatterChart>
    </ChartContainer>
  );
}
