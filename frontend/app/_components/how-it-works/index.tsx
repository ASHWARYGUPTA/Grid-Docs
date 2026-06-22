import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DATASET_STATS,
  OVERFIT_ROWS,
  SURVIVAL_ROWS,
  SURVIVAL_REPO_BASELINE_C_INDEX,
  SURVIVAL_P80_TARGET,
  SURVIVAL_FAIR_COX_C_INDEX,
} from "./data";
import { OverfitScatterChart } from "./overfit-scatter-chart";
import { PrRocChart } from "./pr-roc-chart";
import { ShapBarChart } from "./shap-bar-chart";
import { SurvivalLeaderboardChart } from "./survival-leaderboard-chart";
import { LeakageFixChart } from "./leakage-fix-chart";

const PRODUCTION_MODELS = [
  {
    component: "P(closure)",
    model: "LightGBM + isotonic calibrator",
    version: "lgbm-v1",
    why: "Meets the ≤200 ms response-time budget for the live impact engine with a single serialized artifact. The model-zoo sweep below confirmed gradient boosting plus calibration is the right shape for this data — the remaining gap is a feature-availability ceiling, not a modeling choice.",
  },
  {
    component: "ICT P20/P50/P80",
    model: "Cox Proportional Hazards",
    version: "cox-ph-v1",
    why: "Only model family that correctly handles censored ICT via partial likelihood. After fixing a censoring-time leak in the training pipeline (see below), its true held-out C-index is lower than originally reported — but it remains the right family for this 61.6%-censored target.",
  },
  {
    component: "RCI severity",
    model: "Weighted blend",
    version: null,
    why: "Prior duration, centrality, cascade risk, calibrated P(closure), vehicle complexity, and 2 km density — replaces ASTraM's structural High priority with an operational severity index.",
  },
];

function OverfitTable() {
  return (
    <div className="max-h-105 overflow-y-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead>
            <TableHead className="text-right">Train PR-AUC</TableHead>
            <TableHead className="text-right">CV PR-AUC</TableHead>
            <TableHead className="text-right">Test PR-AUC</TableHead>
            <TableHead className="text-right">Overfit gap</TableHead>
            <TableHead className="text-right">ECE</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[...OVERFIT_ROWS]
            .sort((a, b) => b.testPrAuc - a.testPrAuc)
            .map((row) => (
              <TableRow key={`${row.model}-${row.method}`}>
                <TableCell className="font-medium text-xs">
                  {row.model}
                  <div className="text-muted-foreground font-normal">{row.method}</div>
                </TableCell>
                <TableCell className="text-right text-xs">{row.trainPrAuc?.toFixed(3) ?? "—"}</TableCell>
                <TableCell className="text-right text-xs">{row.cvPrAuc?.toFixed(3) ?? "—"}</TableCell>
                <TableCell className="text-right text-xs font-semibold text-foreground">
                  {row.testPrAuc.toFixed(3)}
                </TableCell>
                <TableCell className="text-right text-xs">
                  {row.overfitGap != null ? row.overfitGap.toFixed(3) : "—"}
                </TableCell>
                <TableCell className="text-right text-xs">{row.ece.toFixed(3)}</TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>
    </div>
  );
}

function SurvivalTable() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Model</TableHead>
          <TableHead>Family</TableHead>
          <TableHead className="text-right">C-index</TableHead>
          <TableHead className="text-right">IBS</TableHead>
          <TableHead className="text-right">P80 coverage</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {[...SURVIVAL_ROWS]
          .sort((a, b) => b.cIndex - a.cIndex)
          .map((row) => (
            <TableRow key={row.model}>
              <TableCell className="font-medium text-xs">{row.model}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{row.family}</TableCell>
              <TableCell className="text-right text-xs font-semibold text-foreground">
                {row.cIndex.toFixed(4)}
              </TableCell>
              <TableCell className="text-right text-xs">{row.ibs?.toFixed(4) ?? "—"}</TableCell>
              <TableCell className="text-right text-xs">
                {row.p80Coverage != null ? `${(row.p80Coverage * 100).toFixed(1)}%` : "—"}
              </TableCell>
            </TableRow>
          ))}
      </TableBody>
    </Table>
  );
}

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
            We ran a deep, &ldquo;try everything&rdquo; research pass on{" "}
            <strong className="text-foreground">{DATASET_STATS.rawRows.toLocaleString()} anonymized ASTraM incidents</strong>{" "}
            from Bengaluru: ~30 classifiers for road-closure prediction and ~12 survival models for
            clearance time, an explicit anti-overfitting protocol on every model, and a full
            leakage audit of the production training pipeline. The target{" "}
            <code className="text-xs bg-muted rounded px-1 py-0.5">requires_road_closure</code> is
            highly imbalanced — only <strong className="text-foreground">{DATASET_STATS.closureBaseRate}%</strong>{" "}
            of events need a closure — so accuracy alone is misleading. We report PR-AUC, ROC-AUC,
            F1-macro, and ECE (calibration error), and use only features knowable at incident
            creation time.
          </p>
        </div>

        {/* Dataset */}
        <div className="mt-12 grid sm:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Rows retained</CardDescription>
              <CardTitle className="text-2xl">{DATASET_STATS.retainedPct}%</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              {DATASET_STATS.retainedRows.toLocaleString()} of {DATASET_STATS.rawRows.toLocaleString()} — only
              unparseable timestamps/coords dropped
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Closure base rate</CardDescription>
              <CardTitle className="text-2xl">{DATASET_STATS.closureBaseRate}%</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              A dummy &ldquo;always no closure&rdquo; model scores ~91.7% accuracy
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Right-censored ICT</CardDescription>
              <CardTitle className="text-2xl">{DATASET_STATS.censoredIctPct}%</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              No observed clearance time — drives the Cox PH choice
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Leakage-safe features</CardDescription>
              <CardTitle className="text-2xl">{DATASET_STATS.features}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Only knowable at incident start — time-ordered priors, no future leakage
            </CardContent>
          </Card>
        </div>

        {/* Task A: signal ceiling */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">
            Task A — Road closure classification: a signal ceiling, not a modeling failure
          </h3>
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed max-w-3xl">
            We swept linear models, random/extra forests, four gradient-boosting libraries, eight
            resampling strategies (SMOTE family, under-sampling), three deep-learning architectures,
            and a tabular foundation model (TabPFN). The result: <strong className="text-foreground">every
            model clusters at PR-AUC 0.26–0.31</strong>, regardless of complexity. When linear
            regression and a heavily-tuned LightGBM land in the same band, the features — not the
            model — are the bottleneck. More hyperparameter search will not move this number;
            new data (live speed feeds, real OSM betweenness, weather) would.
          </p>
          <Card className="mt-5">
            <CardHeader>
              <CardTitle className="text-base">Train vs. CV PR-AUC — the overfit-gap diagnostic</CardTitle>
              <CardDescription>
                Each point is one trained model. Points near the dashed y=x line generalize
                cleanly; points far below it (high train score, low CV score) memorized noise in
                the 676 positive examples rather than learning real structure.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="chart">
                <TabsList>
                  <TabsTrigger value="chart">Chart</TabsTrigger>
                  <TabsTrigger value="table">Raw data</TabsTrigger>
                </TabsList>
                <TabsContent value="chart">
                  <OverfitScatterChart />
                </TabsContent>
                <TabsContent value="table">
                  <OverfitTable />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
          <ul className="mt-6 space-y-2 text-sm text-muted-foreground max-w-3xl">
            <li>
              <strong className="text-foreground">LightGBM + SMOTE</strong> is the practical pick —
              PR-AUC 0.308 (tied for best), F1-macro 0.648 (best in the sweep), and ECE 0.027 — four
              times better calibrated than the raw Optuna-tuned winner.
            </li>
            <li>
              The <strong className="text-foreground">Optuna-tuned LightGBM</strong> reports the
              highest raw PR-AUC (0.309) but its overfit gap (train 0.91 vs CV 0.36) shows most of
              that score is memorization, not generalization — we don&rsquo;t recommend shipping it
              as-is.
            </li>
            <li>
              <strong className="text-foreground">Deep learning underperformed</strong>: TabNet,
              FT-Transformer, and a focal-loss MLP all scored below the tree ensembles on this
              tabular, sparse-feature, 8k-row corpus — exactly where gradient boosting is expected
              to win.
            </li>
            <li>
              High accuracy (~92%) across nearly every model confirms the imbalance trap — it must
              never be used for model selection on this target.
            </li>
          </ul>
        </div>

        {/* PR / ROC + SHAP */}
        <div className="mt-16 grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Precision–Recall &amp; ROC</CardTitle>
              <CardDescription>Three representative models on the held-out test split.</CardDescription>
            </CardHeader>
            <CardContent>
              <PrRocChart />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">What drives the closure score</CardTitle>
              <CardDescription>Mean |SHAP value| — top 12 features, tuned LightGBM.</CardDescription>
            </CardHeader>
            <CardContent>
              <ShapBarChart />
            </CardContent>
          </Card>
        </div>

        {/* Task B */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">
            Task B — Incident clearance time: a fair re-run of the survival model zoo
          </h3>
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed max-w-3xl">
            61.6% of incidents never observe a close time — Cox PH and friends handle this via
            partial likelihood; a naive regressor would just chase imputed durations. We re-ran the
            full survival zoo (Cox variants, AFT, Random Survival Forest, gradient-boosted
            survival, XGBoost AFT) on the <strong className="text-foreground">exact same
            train/validation/test split</strong> used for Task A, so the comparison to the
            originally documented baseline is apples-to-apples.
          </p>
          <Card className="mt-5">
            <CardHeader>
              <CardTitle className="text-base">C-index by model</CardTitle>
              <CardDescription>
                Red line marks the originally documented Cox PH baseline (0.7307). No model in this
                fair re-run reaches it — a methodology finding, not a defeat (see below).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="chart">
                <TabsList>
                  <TabsTrigger value="chart">Chart</TabsTrigger>
                  <TabsTrigger value="table">Raw data</TabsTrigger>
                </TabsList>
                <TabsContent value="chart">
                  <SurvivalLeaderboardChart />
                </TabsContent>
                <TabsContent value="table">
                  <SurvivalTable />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
          <ul className="mt-6 space-y-2 text-sm text-muted-foreground max-w-3xl">
            <li>
              <strong className="text-foreground">GradientBoostingSurvivalAnalysis</strong> (Cox
              loss) wins the fair re-run at C-index {SURVIVAL_ROWS[0]?.cIndex.toFixed(3)} — ahead of
              a from-scratch Cox PH on the same split ({SURVIVAL_FAIR_COX_C_INDEX.toFixed(3)}),
              but still short of the originally documented {SURVIVAL_REPO_BASELINE_C_INDEX}.
            </li>
            <li>
              That gap is explained below: the original number was partly inflated by training-time
              leakage, not a better model.
            </li>
            <li>
              <strong className="text-foreground">P80 coverage</strong> — the PRD&rsquo;s ≥{SURVIVAL_P80_TARGET}%
              gate — passes for every model except XGBoost AFT (57%), which we therefore reject
              for clearance-band staging despite a competitive C-index.
            </li>
          </ul>
        </div>

        {/* Leakage fix */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">
            What we found auditing the production training code
          </h3>
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed max-w-3xl">
            The live training pipeline (
            <code className="text-xs bg-muted rounded px-1 py-0.5">
              backend/src/grid_unlocked/learning/training_core.py
            </code>
            ) computed corridor×cause priors over the <em>entire</em> corpus at once, so an early
            incident&rsquo;s features could be built from outcomes that happened months later — a
            training-time leak the row-by-row denylist checks don&rsquo;t catch. Cox PH also filled
            every censored incident&rsquo;s duration with a population prior instead of its true
            observed window, artificially shrinking duration variance. We fixed both: priors are now
            time-ordered expanding statistics (past-only), and censored rows carry their real
            elapsed-to-last-observed time.
          </p>
          <Card className="mt-5">
            <CardHeader>
              <CardTitle className="text-base">Before vs. after, same held-out split</CardTitle>
              <CardDescription>
                Both metrics drop once the leakage is removed — exactly as expected. The model
                didn&rsquo;t get worse; the measurement got honest.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LeakageFixChart />
            </CardContent>
          </Card>
          <ul className="mt-6 space-y-2 text-sm text-muted-foreground max-w-3xl">
            <li>
              Closure PR-AUC: <strong className="text-foreground">0.394 → 0.371</strong> after the
              fix — a 2-point drop, consistent with the Task-A ceiling finding above.
            </li>
            <li>
              Cox C-index: <strong className="text-foreground">0.652 → 0.575</strong> — a larger
              drop, because continuous durations are more sensitive to a leaky prior baked directly
              into the training label.
            </li>
            <li>
              Neither corrected number matches the originally documented baseline exactly, because
              that baseline came from a separate research-notebook pipeline with a different
              feature set — the point of this audit was to stop the <em>production</em> path from
              overstating its own performance, which it was.
            </li>
          </ul>
        </div>

        {/* Production models */}
        <div className="mt-16">
          <h3 className="text-xl font-semibold tracking-tight">
            Production models (AI Impact Engine)
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
            <li>
              The signal-ceiling and leakage findings above are now load-bearing for roadmap
              decisions: the next meaningful gain comes from new features or data, not more model
              tuning on the current corpus.
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
