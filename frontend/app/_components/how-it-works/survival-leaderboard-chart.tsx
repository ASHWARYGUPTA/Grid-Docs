"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  SURVIVAL_REPO_BASELINE_C_INDEX,
  SURVIVAL_ROWS,
} from "./data";

const chartConfig: ChartConfig = {
  cIndex: { label: "C-index", color: "var(--chart-1)" },
};

const sorted = [...SURVIVAL_ROWS].sort((a, b) => b.cIndex - a.cIndex);

export function SurvivalLeaderboardChart() {
  return (
    <ChartContainer config={chartConfig} className="aspect-auto h-105 w-full">
      <BarChart data={sorted} layout="vertical" margin={{ left: 24, right: 32 }}>
        <CartesianGrid horizontal={false} strokeDasharray="3 3" />
        <XAxis type="number" domain={[0, 0.8]} tickFormatter={(v) => v.toFixed(2)} />
        <YAxis
          type="category"
          dataKey="model"
          width={170}
          tick={{ fontSize: 11 }}
          interval={0}
        />
        <ReferenceLine
          x={SURVIVAL_REPO_BASELINE_C_INDEX}
          stroke="var(--destructive)"
          strokeDasharray="4 4"
          label={{
            value: `Documented baseline 0.731`,
            position: "insideTopRight",
            fontSize: 11,
            fill: "var(--destructive)",
          }}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              labelKey="model"
              formatter={(value, name) => [
                typeof value === "number" ? value.toFixed(4) : value,
                name === "cIndex" ? "C-index" : String(name),
              ]}
            />
          }
        />
        <Bar dataKey="cIndex" radius={4}>
          {sorted.map((row) => (
            <Cell
              key={row.model}
              fill={row.cIndex >= SURVIVAL_REPO_BASELINE_C_INDEX ? "var(--chart-3)" : "var(--color-cIndex)"}
            />
          ))}
          <LabelList
            dataKey="cIndex"
            position="right"
            formatter={(v: unknown) => (typeof v === "number" ? v.toFixed(3) : "")}
            fontSize={11}
          />
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
