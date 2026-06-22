"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { LEAKAGE_FIX_CLOSURE, LEAKAGE_FIX_COX } from "./data";

const chartConfig: ChartConfig = {
  documented: { label: "Documented baseline", color: "var(--chart-2)" },
  modelZoo: { label: "Colab model-zoo best", color: "var(--chart-3)" },
  productionBefore: { label: "Production — before fix", color: "var(--chart-4)" },
  productionAfter: { label: "Production — after fix", color: "var(--chart-1)" },
};

type FixStage = { label: string } & Record<string, number | string>;
type FixSource = {
  documented: FixStage;
  modelZoo: FixStage;
  productionBefore: FixStage;
  productionAfter: FixStage;
};

function buildRows(metric: string, source: FixSource) {
  return [
    { stage: "documented", value: source.documented[metric] as number },
    { stage: "modelZoo", value: source.modelZoo[metric] as number },
    { stage: "productionBefore", value: source.productionBefore[metric] as number },
    { stage: "productionAfter", value: source.productionAfter[metric] as number },
  ];
}

function LeakageBars({
  title,
  rows,
  domain,
}: {
  title: string;
  rows: { stage: string; value: number }[];
  domain: [number, number];
}) {
  return (
    <div>
      <p className="text-sm font-medium text-foreground mb-2">{title}</p>
      <ChartContainer config={chartConfig} className="aspect-auto h-55 w-full">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="stage"
            tickFormatter={(stage) => String(chartConfig[stage]?.label ?? stage)}
            tick={{ fontSize: 10 }}
            interval={0}
          />
          <YAxis domain={domain} tickFormatter={(v) => v.toFixed(2)} width={40} />
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                formatter={(value) => [typeof value === "number" ? value.toFixed(4) : value, title]}
                labelFormatter={(stage) => String(chartConfig[stage]?.label ?? stage)}
              />
            }
          />
          <Bar dataKey="value" radius={4}>
            {rows.map((row) => (
              <Cell key={row.stage} fill={`var(--color-${row.stage})`} />
            ))}
            <LabelList
              dataKey="value"
              position="top"
              formatter={(v: unknown) => (typeof v === "number" ? v.toFixed(3) : "")}
              fontSize={11}
            />
          </Bar>
        </BarChart>
      </ChartContainer>
    </div>
  );
}

export function LeakageFixChart() {
  const closureRows = buildRows("prAuc", LEAKAGE_FIX_CLOSURE as unknown as FixSource);
  const coxRows = buildRows("cIndex", LEAKAGE_FIX_COX as unknown as FixSource);

  return (
    <div className="grid sm:grid-cols-2 gap-8">
      <LeakageBars title="Closure model — PR-AUC" rows={closureRows} domain={[0, 0.45]} />
      <LeakageBars title="ICT survival — Cox C-index" rows={coxRows} domain={[0, 0.8]} />
    </div>
  );
}
