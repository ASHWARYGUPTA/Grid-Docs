"use client";

import { Bar, BarChart, CartesianGrid, LabelList, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { SHAP_TOP12 } from "./data";

const chartConfig: ChartConfig = {
  meanAbsShap: { label: "Mean |SHAP value|", color: "var(--chart-1)" },
};

export function ShapBarChart() {
  if (SHAP_TOP12.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground border rounded-lg">
        SHAP data not yet loaded.
      </div>
    );
  }

  const sorted = [...SHAP_TOP12].sort((a, b) => b.meanAbsShap - a.meanAbsShap);

  return (
    <ChartContainer config={chartConfig} className="aspect-auto h-90 w-full">
      <BarChart data={sorted} layout="vertical" margin={{ left: 24, right: 32 }}>
        <CartesianGrid horizontal={false} strokeDasharray="3 3" />
        <XAxis type="number" tickFormatter={(v) => v.toFixed(2)} />
        <YAxis type="category" dataKey="feature" width={150} tick={{ fontSize: 11 }} interval={0} />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              labelKey="feature"
              formatter={(value) => [typeof value === "number" ? value.toFixed(4) : value, "Mean |SHAP|"]}
            />
          }
        />
        <Bar dataKey="meanAbsShap" fill="var(--color-meanAbsShap)" radius={4}>
          <LabelList
            dataKey="meanAbsShap"
            position="right"
            formatter={(v: unknown) => (typeof v === "number" ? v.toFixed(3) : "")}
            fontSize={11}
          />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
