import Image from "next/image";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface ClosureRow {
  model: string;
  accuracy: string;
  prAuc: string;
  rocAuc: string;
  f1: string;
  ece: string;
  winner?: ("accuracy" | "prAuc" | "rocAuc" | "f1" | "ece")[];
}

const CLOSURE_ROWS: ClosureRow[] = [
  { model: "Logistic Regression", accuracy: "91.68%", prAuc: "0.1777", rocAuc: "0.6822", f1: "0.4783", ece: "0.00670" },
  { model: "Random Forest", accuracy: "91.80%", prAuc: "0.2596", rocAuc: "0.7324", f1: "0.5067", ece: "0.00804" },
  { model: "XGBoost", accuracy: "91.80%", prAuc: "0.2600", rocAuc: "0.7313", f1: "0.5133", ece: "0.01086" },
  { model: "LightGBM", accuracy: "81.59%", prAuc: "0.2640", rocAuc: "0.7515", f1: "0.6009", ece: "0.19417" },
  { model: "MLP", accuracy: "91.68%", prAuc: "0.1121", rocAuc: "0.5888", f1: "0.4783", ece: "0.04864" },
  {
    model: "Stacking (Raw)",
    accuracy: "91.80%",
    prAuc: "0.2822",
    rocAuc: "0.7536",
    f1: "0.5067",
    ece: "0.01112",
    winner: ["accuracy", "prAuc", "rocAuc"],
  },
  {
    model: "Stacking (Calibrated)",
    accuracy: "88.93%",
    prAuc: "0.2767",
    rocAuc: "0.7471",
    f1: "0.6178",
    ece: "0.00456",
    winner: ["f1", "ece"],
  },
];

function Cell({ value, bold }: { value: string; bold?: boolean }) {
  return <TableCell className={bold ? "font-semibold text-foreground" : undefined}>{value}</TableCell>;
}

function ClosureTable() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Model</TableHead>
          <TableHead className="text-right">Accuracy</TableHead>
          <TableHead className="text-right">PR-AUC</TableHead>
          <TableHead className="text-right">ROC-AUC</TableHead>
          <TableHead className="text-right">F1-Macro</TableHead>
          <TableHead className="text-right">ECE</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {CLOSURE_ROWS.map((row) => (
          <TableRow key={row.model}>
            <TableCell className={row.winner ? "font-semibold text-foreground" : "font-medium"}>
              {row.model}
            </TableCell>
            <Cell value={row.accuracy} bold={row.winner?.includes("accuracy")} />
            <Cell value={row.prAuc} bold={row.winner?.includes("prAuc")} />
            <Cell value={row.rocAuc} bold={row.winner?.includes("rocAuc")} />
            <Cell value={row.f1} bold={row.winner?.includes("f1")} />
            <Cell value={row.ece} bold={row.winner?.includes("ece")} />
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function IctTable() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Model</TableHead>
          <TableHead>Metric</TableHead>
          <TableHead className="text-right">Result</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell className="font-semibold text-foreground">Cox Proportional Hazards</TableCell>
          <TableCell>C-Index</TableCell>
          <TableCell className="text-right font-semibold text-foreground">0.7307</TableCell>
        </TableRow>
        <TableRow>
          <TableCell className="font-semibold text-foreground">Cox Proportional Hazards</TableCell>
          <TableCell>P80 coverage</TableCell>
          <TableCell className="text-right font-semibold text-foreground">100%</TableCell>
        </TableRow>
        <TableRow>
          <TableCell className="font-medium">LightGBM Regressor</TableCell>
          <TableCell>MAE (observed only)</TableCell>
          <TableCell className="text-right">8,633 min (~6 days)</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}

const PRODUCTION_MODELS = [
  {
    component: "P(closure)",
    model: "LightGBM + isotonic calibrator",
    version: "lgbm-v1",
    why: "Meets the ≤200 ms M03 inference SLA with a single serialized artifact. Offline evaluation showed LightGBM ROC-AUC 0.752 (within 0.002 of the stack). Isotonic calibration on the validation fold brings ECE in line with the stacked ensemble without multi-model inference overhead. Stacking wins marginally on PR-AUC (+0.02) but adds latency and deployment complexity inappropriate for hackathon MVP.",
  },
  {
    component: "ICT P20/P50/P80",
    model: "Cox Proportional Hazards",
    version: "cox-ph-v1",
    why: "Only model that correctly handles censored ICT. C-Index 0.73 and conservative P80 bands. LightGBM regressor rejected (MAE ~6 days).",
  },
  {
    component: "RCI severity",
    model: "Weighted blend",
    version: null,
    why: "Prior duration, centrality, cascade risk, calibrated P(closure), vehicle complexity, and 2 km density — replaces ASTraM's structural High priority with an operational severity index.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20 sm:py-28 border-t">
      <div className="mx-auto max-w-5xl px-6">
        <div className="max-w-2xl">
          <Badge variant="outline" className="mb-3">
            How it works
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            The ML research behind every recommendation
          </h2>
          <p className="mt-4 text-muted-foreground leading-relaxed">
            We evaluated seven classifiers and two duration models on{" "}
            <strong className="text-foreground">8,173 anonymized ASTraM incidents</strong> from
            Bengaluru. The target <code className="text-xs bg-muted rounded px-1 py-0.5">requires_road_closure</code>{" "}
            is highly imbalanced — only <strong className="text-foreground">8.27%</strong> of events
            need a closure — so accuracy alone is misleading (a model that always predicts
            &ldquo;no closure&rdquo; scores ~91.7%). We report PR-AUC, ROC-AUC, F1-macro, and ECE
            (calibration error), and use only features knowable at incident creation time.
          </p>
        </div>

        {/* Dataset */}
        <div className="mt-12 grid sm:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Raw corpus</CardDescription>
              <CardTitle className="text-2xl">8,173</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Normalized ASTraM events, Bengaluru
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Closure base rate</CardDescription>
              <CardTitle className="text-2xl">8.27%</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Why accuracy alone is the wrong metric here
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Right-censored ICT records</CardDescription>
              <CardTitle className="text-2xl">61.6%</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              No observed clearance time — drives the Cox PH choice
            </CardContent>
          </Card>
        </div>

        <p className="mt-6 text-sm text-muted-foreground leading-relaxed">
          Engineered features include spatio-temporal density (2 km / 5 km Haversine overlap),
          KMeans region clusters, cyclical time encoding, NLP keyword flags from descriptions,
          corridor centrality, vehicle complexity, and ICT survival fields.
        </p>

        {/* Task A */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">
            Task A — Road closure classification
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            60/20/20 train/validation/test split, stratified on the closure label.
          </p>
          <Card className="mt-5">
            <CardContent className="pt-6 overflow-x-auto">
              <ClosureTable />
            </CardContent>
          </Card>

          <div className="mt-6 rounded-lg border bg-card overflow-hidden">
            <Image
              src="/model-evaluation-curves.png"
              alt="ROC and Precision-Recall curves for closure classifiers"
              width={1024}
              height={444}
              className="w-full h-auto"
            />
          </div>

          <ul className="mt-6 space-y-2 text-sm text-muted-foreground">
            <li>
              <strong className="text-foreground">Stacking (Raw)</strong> achieved the best PR-AUC
              (0.282) and ROC-AUC (0.754) — ~3.4× better than random on the minority class (base
              rate 0.083).
            </li>
            <li>
              <strong className="text-foreground">Stacking (Calibrated)</strong> achieved the best
              F1-macro (0.618) and calibration (ECE 0.005) — best for commander-facing
              probabilities.
            </li>
            <li>
              <strong className="text-foreground">LightGBM</strong> ranked second on ROC-AUC
              (0.752) but was poorly calibrated without isotonic post-processing (ECE 0.19).
            </li>
            <li>
              <strong className="text-foreground">MLP</strong> underperformed tree ensembles on
              this tabular, sparse-feature corpus.
            </li>
            <li>
              High accuracy (~92%) across most models confirms the imbalance trap — it must not be
              used for model selection.
            </li>
          </ul>
        </div>

        {/* Task B */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">
            Task B — Incident clearance time (ICT)
          </h3>
          <Card className="mt-5">
            <CardContent className="pt-6 overflow-x-auto">
              <IctTable />
            </CardContent>
          </Card>
          <ul className="mt-6 space-y-2 text-sm text-muted-foreground">
            <li>
              <strong className="text-foreground">61.6% of incidents are right-censored</strong>{" "}
              (no observed end time). Cox PH handles censoring via partial likelihood; the point
              regressor chases imputed durations and is not deployable.
            </li>
            <li>
              Cox C-Index <strong className="text-foreground">0.73</strong> exceeds our promotion
              threshold (≥ 0.68) for ranking clearance order and producing P20/P50/P80 bands for
              field briefing.
            </li>
          </ul>
        </div>

        {/* Production models */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">
            Production models (M03 ImpactEngine)
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Artifacts live in <code className="text-xs bg-muted rounded px-1 py-0.5">backend/models/v1/</code>{" "}
            and are loaded by the API at startup.
          </p>
          <div className="mt-5 space-y-4">
            {PRODUCTION_MODELS.map((row) => (
              <Card key={row.component}>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <CardTitle className="text-base">{row.component}</CardTitle>
                    <Badge variant="secondary">{row.model}</Badge>
                    {row.version && (
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {row.version}
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground leading-relaxed">
                  {row.why}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Operational implications */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">Operational implications</h3>
          <ul className="mt-5 space-y-2 text-sm text-muted-foreground">
            <li>
              Closure prediction is{" "}
              <strong className="text-foreground">triage, not autopilot</strong> — use calibrated
              P(closure) with human approval (shadow mode by default).
            </li>
            <li>
              Thresholds: <code className="text-xs bg-muted rounded px-1 py-0.5">p_closure &gt; 0.35</code>{" "}
              triggers diversion auto-suggest; composite gates drive CRITICAL alerts on named
              corridors at peak hour.
            </li>
            <li>
              Planned events (36% closure rate) route to template-based package generation rather
              than repeated live closure inference.
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
