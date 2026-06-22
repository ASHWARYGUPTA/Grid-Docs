"use client";

import { useState } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CURVE_MODELS } from "./data";

const MODEL_NAMES = Object.keys(CURVE_MODELS);

const chartConfig: ChartConfig = {
  LightGBM: { label: "LightGBM", color: "var(--chart-1)" },
  XGBoost: { label: "XGBoost", color: "var(--chart-4)" },
  LogRegBal: { label: "LogReg (balanced)", color: "var(--chart-2)" },
};

function mergeCurves(kind: "pr" | "roc") {
  // Each model's curve has its own x-sampling (recall or FPR); merge into one
  // array keyed by a shared x-bucket so all three lines plot on one chart.
  const buckets = 40;
  const merged: Record<string, number>[] = Array.from({ length: buckets + 1 }, (_, i) => ({
    x: i / buckets,
  }));
  for (const name of MODEL_NAMES) {
    const points = CURVE_MODELS[name][kind];
    if (points.length === 0) continue;
    for (let i = 0; i <= buckets; i++) {
      const targetX = i / buckets;
      const nearest = points.reduce((best, p) =>
        Math.abs(p.x - targetX) < Math.abs(best.x - targetX) ? p : best
      );
      merged[i][name] = nearest.y;
    }
  }
  return merged;
}

export function PrRocChart() {
  const [tab, setTab] = useState<"pr" | "roc">("pr");
  const data = mergeCurves(tab);
  const hasData = MODEL_NAMES.some((name) => CURVE_MODELS[name][tab].length > 0);

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as "pr" | "roc")}>
      <div className="flex items-center justify-between gap-4 flex-wrap mb-3">
        <TabsList>
          <TabsTrigger value="pr">Precision–Recall</TabsTrigger>
          <TabsTrigger value="roc">ROC</TabsTrigger>
        </TabsList>
        <div className="flex gap-3 text-xs text-muted-foreground">
          {MODEL_NAMES.map((name) => (
            <span key={name}>
              {CURVE_MODELS[name].label} AP={CURVE_MODELS[name].ap.toFixed(3)}
            </span>
          ))}
        </div>
      </div>
      <TabsContent value={tab}>
        {hasData ? (
          <ChartContainer config={chartConfig} className="aspect-auto h-80 w-full">
            <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="x"
                type="number"
                domain={[0, 1]}
                tickFormatter={(v) => v.toFixed(1)}
                label={{
                  value: tab === "pr" ? "Recall" : "False positive rate",
                  position: "insideBottom",
                  offset: -4,
                  fontSize: 12,
                }}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={(v) => v.toFixed(1)}
                label={{
                  value: tab === "pr" ? "Precision" : "True positive rate",
                  angle: -90,
                  position: "insideLeft",
                  fontSize: 12,
                }}
              />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              {MODEL_NAMES.map((name) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={`var(--color-${name})`}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ChartContainer>
        ) : (
          <div className="flex h-80 items-center justify-center text-sm text-muted-foreground border rounded-lg">
            Curve data not yet loaded — see AP scores above.
          </div>
        )}
      </TabsContent>
    </Tabs>
  );
}
