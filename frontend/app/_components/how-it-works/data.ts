// Research data backing the "How it works" landing section.
// All numbers are static snapshots from the research session — see comments
// on each block for provenance. Re-run the notebooks under research/ to refresh.

export const DATASET_STATS = {
  rawRows: 8173,
  retainedRows: 8057, // research/01_eda_feature_engineering.ipynb — row-retention audit
  retainedPct: 98.6,
  closureBaseRate: 8.27,
  censoredIctPct: 61.6,
  features: 35,
};

// --- Task A: overfit-gap scatter ------------------------------------------
// Source: research/02_model_zoo_colab.ipynb, full `lbA` leaderboard
// (Google Colab session, model-zoo run). Each point is one trained model;
// overfit_gap = train_PR_AUC − cv_PR_AUC (≈0 healthy, large positive = overfit).
export type OverfitRow = {
  model: string;
  method: string;
  trainPrAuc: number | null;
  cvPrAuc: number | null;
  testPrAuc: number;
  overfitGap: number | null;
  ece: number;
  family: "linear" | "forest" | "gbdt" | "resample" | "deep" | "foundation" | "ensemble" | "baseline";
};

// Source: research/02_model_zoo_colab.ipynb, full `lbA` leaderboard
// extracted directly from the live Colab session (32 model rows).
export const OVERFIT_ROWS: OverfitRow[] = [
  { model: "LightGBM (Optuna-tuned)", method: "tuned+scale_pos_weight", trainPrAuc: 0.908303, cvPrAuc: 0.362176, testPrAuc: 0.309002, overfitGap: 0.546127, ece: 0.112079, family: "gbdt" },
  { model: "LightGBM + SMOTE", method: "resample(SMOTE)", trainPrAuc: 0.871463, cvPrAuc: 0.349121, testPrAuc: 0.308065, overfitGap: 0.522342, ece: 0.027326, family: "resample" },
  { model: "XGBoost", method: "scale_pos_weight", trainPrAuc: 0.920206, cvPrAuc: 0.324572, testPrAuc: 0.306029, overfitGap: 0.595635, ece: 0.103327, family: "gbdt" },
  { model: "RandomForest", method: "class_weight", trainPrAuc: 0.81507, cvPrAuc: 0.334814, testPrAuc: 0.305512, overfitGap: 0.480256, ece: 0.120408, family: "forest" },
  { model: "BalancedRandomForest", method: "resample(under)", trainPrAuc: 0.859247, cvPrAuc: 0.336682, testPrAuc: 0.304103, overfitGap: 0.522565, ece: 0.253608, family: "resample" },
  { model: "LightGBM + SMOTEENN", method: "resample(SMOTEENN)", trainPrAuc: 0.691597, cvPrAuc: 0.332038, testPrAuc: 0.30392, overfitGap: 0.359559, ece: 0.048952, family: "resample" },
  { model: "LightGBM + SMOTETomek", method: "resample(SMOTETomek)", trainPrAuc: 0.854671, cvPrAuc: 0.340532, testPrAuc: 0.301236, overfitGap: 0.514139, ece: 0.030128, family: "resample" },
  { model: "EasyEnsemble", method: "resample(under)", trainPrAuc: 0.306389, cvPrAuc: 0.279492, testPrAuc: 0.300589, overfitGap: 0.026897, ece: 0.393769, family: "resample" },
  { model: "Stacking (lgbm+xgb+rf)", method: "stacking", trainPrAuc: 0.923363, cvPrAuc: null, testPrAuc: 0.298945, overfitGap: 0.624418, ece: 0.344532, family: "ensemble" },
  { model: "LightGBM + ADASYN", method: "resample(ADASYN)", trainPrAuc: 0.889869, cvPrAuc: 0.36255, testPrAuc: 0.296811, overfitGap: 0.527318, ece: 0.026115, family: "resample" },
  { model: "LightGBM + BorderlineSMOTE", method: "resample(BorderlineSMOTE)", trainPrAuc: 0.86439, cvPrAuc: 0.35347, testPrAuc: 0.295199, overfitGap: 0.510919, ece: 0.029339, family: "resample" },
  { model: "CatBoost", method: "auto_class_weights", trainPrAuc: 0.949538, cvPrAuc: 0.334087, testPrAuc: 0.294376, overfitGap: 0.615452, ece: 0.098443, family: "gbdt" },
  { model: "LightGBM", method: "is_unbalance", trainPrAuc: 0.971134, cvPrAuc: 0.337751, testPrAuc: 0.29427, overfitGap: 0.633383, ece: 0.08675, family: "gbdt" },
  { model: "LightGBM", method: "scale_pos_weight", trainPrAuc: 0.971134, cvPrAuc: 0.334875, testPrAuc: 0.29427, overfitGap: 0.636259, ece: 0.08675, family: "gbdt" },
  { model: "LightGBM + RandomUnderSampler", method: "resample(RandomUnderSampler)", trainPrAuc: 0.437309, cvPrAuc: 0.267135, testPrAuc: 0.292014, overfitGap: 0.170174, ece: 0.302382, family: "resample" },
  { model: "LightGBM", method: "class_weight", trainPrAuc: 0.963054, cvPrAuc: 0.343024, testPrAuc: 0.290518, overfitGap: 0.620031, ece: 0.090934, family: "gbdt" },
  { model: "LightGBM + SVMSMOTE", method: "resample(SVMSMOTE)", trainPrAuc: 0.840424, cvPrAuc: 0.352205, testPrAuc: 0.28773, overfitGap: 0.488219, ece: 0.022673, family: "resample" },
  { model: "XGBoost (focal γ=2)", method: "focal_loss", trainPrAuc: 0.780968, cvPrAuc: 0.31683, testPrAuc: 0.286602, overfitGap: 0.464138, ece: 0.027435, family: "gbdt" },
  { model: "HistGradientBoosting", method: "class_weight", trainPrAuc: 0.44113, cvPrAuc: 0.318345, testPrAuc: 0.283351, overfitGap: 0.122785, ece: 0.295778, family: "gbdt" },
  { model: "ExtraTrees", method: "class_weight", trainPrAuc: 0.788424, cvPrAuc: 0.329088, testPrAuc: 0.276054, overfitGap: 0.459337, ece: 0.201197, family: "forest" },
  { model: "LogisticRegression", method: "none", trainPrAuc: 0.289334, cvPrAuc: 0.279709, testPrAuc: 0.270714, overfitGap: 0.009625, ece: 0.0118, family: "linear" },
  { model: "LinearSVC", method: "class_weight", trainPrAuc: 0.273402, cvPrAuc: 0.268864, testPrAuc: 0.258276, overfitGap: 0.004538, ece: 0.409857, family: "linear" },
  { model: "LogisticRegression (L1)", method: "class_weight", trainPrAuc: 0.271889, cvPrAuc: 0.269544, testPrAuc: 0.25609, overfitGap: 0.002345, ece: 0.330053, family: "linear" },
  { model: "LogisticRegression", method: "class_weight", trainPrAuc: 0.271911, cvPrAuc: 0.269857, testPrAuc: 0.255656, overfitGap: 0.002055, ece: 0.32961, family: "linear" },
  { model: "MLP (focal loss)", method: "focal_loss", trainPrAuc: null, cvPrAuc: null, testPrAuc: 0.238359, overfitGap: null, ece: 0.220318, family: "deep" },
  { model: "GaussianNB", method: "none", trainPrAuc: 0.219962, cvPrAuc: 0.224478, testPrAuc: 0.20467, overfitGap: -0.004516, ece: 0.825804, family: "linear" },
  { model: "TabNet", method: "balanced_sampling", trainPrAuc: null, cvPrAuc: null, testPrAuc: 0.191243, overfitGap: null, ece: 0.243786, family: "deep" },
  { model: "KNN (k=15)", method: "none", trainPrAuc: 0.34195, cvPrAuc: 0.245582, testPrAuc: 0.189982, overfitGap: 0.096368, ece: 0.036311, family: "linear" },
  { model: "RUSBoost", method: "resample(under)", trainPrAuc: 0.190486, cvPrAuc: 0.204566, testPrAuc: 0.167461, overfitGap: -0.01408, ece: 0.129975, family: "resample" },
  { model: "FT-Transformer", method: "focal_loss", trainPrAuc: null, cvPrAuc: null, testPrAuc: 0.138403, overfitGap: null, ece: 0.095603, family: "deep" },
  { model: "LightGBM + NearMiss", method: "resample(NearMiss)", trainPrAuc: 0.11962, cvPrAuc: 0.09674, testPrAuc: 0.092781, overfitGap: 0.022879, ece: 0.633339, family: "resample" },
  { model: "Dummy (always majority)", method: "baseline", trainPrAuc: 0.074059, cvPrAuc: null, testPrAuc: 0.073821, overfitGap: 0.000237, ece: 0.073821, family: "baseline" },
];

// --- Task A: PR / ROC curves + SHAP -----------------------------------------
// Source: research/02_model_zoo_colab.ipynb extraction cell (Colab session),
// recall/precision and FPR/TPR points downsampled to ~40 pts per curve.
export type CurvePoint = { x: number; y: number };
export type CurveModel = { label: string; ap: number; pr: CurvePoint[]; roc: CurvePoint[] };
// Keys are sanitized identifiers (used as recharts dataKeys / shadcn chart
// --color-<key> CSS vars); `label` carries the display name shown in legends.
export const CURVE_MODELS: Record<string, CurveModel> = {
  LightGBM: { label: "LightGBM", ap: 0.309, pr: [{"x":1.0,"y":0.0738},{"x":1.0,"y":0.0758},{"x":0.9748,"y":0.0759},{"x":0.9748,"y":0.078},{"x":0.9748,"y":0.0802},{"x":0.9664,"y":0.0819},{"x":0.958,"y":0.0838},{"x":0.9496,"y":0.0857},{"x":0.9412,"y":0.0876},{"x":0.916,"y":0.0881},{"x":0.916,"y":0.0912},{"x":0.916,"y":0.0945},{"x":0.9076,"y":0.097},{"x":0.8739,"y":0.097},{"x":0.8655,"y":0.0999},{"x":0.8319,"y":0.1001},{"x":0.8151,"y":0.1023},{"x":0.7983,"y":0.1047},{"x":0.7563,"y":0.1039},{"x":0.7227,"y":0.1042},{"x":0.7227,"y":0.1098},{"x":0.7227,"y":0.1159},{"x":0.6975,"y":0.1184},{"x":0.6723,"y":0.1212},{"x":0.6639,"y":0.1276},{"x":0.6471,"y":0.1334},{"x":0.6218,"y":0.1381},{"x":0.5966,"y":0.1434},{"x":0.5966,"y":0.1564},{"x":0.563,"y":0.1622},{"x":0.5294,"y":0.1698},{"x":0.5042,"y":0.1818},{"x":0.4874,"y":0.2007},{"x":0.4622,"y":0.2218},{"x":0.4286,"y":0.2464},{"x":0.3697,"y":0.2667},{"x":0.3361,"y":0.3226},{"x":0.2773,"y":0.3976},{"x":0.2185,"y":0.619},{"x":0.0,"y":1.0}], roc: [{"x":0.0,"y":0.0},{"x":0.0007,"y":0.0504},{"x":0.004,"y":0.084},{"x":0.0074,"y":0.1849},{"x":0.0127,"y":0.2185},{"x":0.0147,"y":0.2521},{"x":0.0268,"y":0.2689},{"x":0.0382,"y":0.3025},{"x":0.0476,"y":0.3193},{"x":0.0697,"y":0.3445},{"x":0.075,"y":0.3697},{"x":0.0998,"y":0.395},{"x":0.1085,"y":0.437},{"x":0.1293,"y":0.4538},{"x":0.1393,"y":0.479},{"x":0.1634,"y":0.4958},{"x":0.1942,"y":0.5126},{"x":0.2197,"y":0.5378},{"x":0.2317,"y":0.5546},{"x":0.2378,"y":0.5798},{"x":0.2894,"y":0.5966},{"x":0.3182,"y":0.6303},{"x":0.3463,"y":0.6471},{"x":0.367,"y":0.6723},{"x":0.3999,"y":0.6891},{"x":0.4313,"y":0.7059},{"x":0.4963,"y":0.7395},{"x":0.5251,"y":0.7563},{"x":0.5392,"y":0.7815},{"x":0.564,"y":0.8067},{"x":0.5961,"y":0.8487},{"x":0.6236,"y":0.8655},{"x":0.6564,"y":0.8824},{"x":0.6711,"y":0.9076},{"x":0.7689,"y":0.9244},{"x":0.783,"y":0.9496},{"x":0.85,"y":0.958},{"x":0.8861,"y":0.9664},{"x":0.9518,"y":0.9916},{"x":1.0,"y":1.0}] },
  XGBoost: { label: "XGBoost", ap: 0.2865, pr: [{"x":1.0,"y":0.0738},{"x":0.9832,"y":0.0745},{"x":0.9832,"y":0.0765},{"x":0.9664,"y":0.0773},{"x":0.9664,"y":0.0795},{"x":0.9412,"y":0.0797},{"x":0.9244,"y":0.0809},{"x":0.9076,"y":0.0819},{"x":0.9076,"y":0.0846},{"x":0.8992,"y":0.0866},{"x":0.8571,"y":0.0854},{"x":0.8487,"y":0.0875},{"x":0.8403,"y":0.0899},{"x":0.8403,"y":0.0934},{"x":0.8151,"y":0.0942},{"x":0.7899,"y":0.095},{"x":0.7731,"y":0.097},{"x":0.7479,"y":0.0982},{"x":0.7479,"y":0.1029},{"x":0.7311,"y":0.1056},{"x":0.7143,"y":0.1086},{"x":0.7059,"y":0.1132},{"x":0.6807,"y":0.1155},{"x":0.6555,"y":0.1184},{"x":0.6471,"y":0.1246},{"x":0.6471,"y":0.1334},{"x":0.6218,"y":0.1381},{"x":0.5966,"y":0.1434},{"x":0.5882,"y":0.1545},{"x":0.5798,"y":0.1675},{"x":0.563,"y":0.1806},{"x":0.5126,"y":0.1848},{"x":0.4538,"y":0.1869},{"x":0.437,"y":0.2097},{"x":0.4118,"y":0.2379},{"x":0.3866,"y":0.2788},{"x":0.3193,"y":0.3065},{"x":0.3025,"y":0.4337},{"x":0.1933,"y":0.5476},{"x":0.0,"y":1.0}], roc: [{"x":0.0,"y":0.0},{"x":0.0033,"y":0.0504},{"x":0.0054,"y":0.1008},{"x":0.008,"y":0.1429},{"x":0.0107,"y":0.1597},{"x":0.0161,"y":0.2017},{"x":0.0174,"y":0.2269},{"x":0.0201,"y":0.2773},{"x":0.0295,"y":0.2941},{"x":0.0583,"y":0.3193},{"x":0.0643,"y":0.3445},{"x":0.0777,"y":0.3782},{"x":0.0877,"y":0.395},{"x":0.1293,"y":0.4202},{"x":0.152,"y":0.4454},{"x":0.1641,"y":0.4622},{"x":0.1661,"y":0.4874},{"x":0.1788,"y":0.5126},{"x":0.1875,"y":0.5378},{"x":0.1956,"y":0.5546},{"x":0.2411,"y":0.5798},{"x":0.2947,"y":0.605},{"x":0.3115,"y":0.6303},{"x":0.3744,"y":0.6471},{"x":0.4099,"y":0.6723},{"x":0.4226,"y":0.6975},{"x":0.4682,"y":0.7227},{"x":0.5198,"y":0.7395},{"x":0.5573,"y":0.7647},{"x":0.5928,"y":0.7899},{"x":0.6296,"y":0.8151},{"x":0.6899,"y":0.8403},{"x":0.7328,"y":0.8655},{"x":0.7388,"y":0.8908},{"x":0.8131,"y":0.9076},{"x":0.8573,"y":0.9244},{"x":0.8667,"y":0.9496},{"x":0.8875,"y":0.9664},{"x":0.9625,"y":0.9832},{"x":1.0,"y":1.0}] },
  LogRegBal: { label: "LogReg (balanced)", ap: 0.2557, pr: [{"x":1.0,"y":0.0738},{"x":0.9916,"y":0.0751},{"x":0.9832,"y":0.0765},{"x":0.9748,"y":0.078},{"x":0.9748,"y":0.0802},{"x":0.9664,"y":0.0818},{"x":0.9664,"y":0.0843},{"x":0.9664,"y":0.0869},{"x":0.9412,"y":0.0874},{"x":0.9328,"y":0.0895},{"x":0.9244,"y":0.0917},{"x":0.9076,"y":0.0933},{"x":0.8824,"y":0.0941},{"x":0.8571,"y":0.0949},{"x":0.8403,"y":0.0967},{"x":0.8235,"y":0.0988},{"x":0.8235,"y":0.103},{"x":0.8151,"y":0.1066},{"x":0.7899,"y":0.1083},{"x":0.7815,"y":0.1125},{"x":0.7647,"y":0.1158},{"x":0.7227,"y":0.1156},{"x":0.7143,"y":0.1209},{"x":0.6975,"y":0.1254},{"x":0.6639,"y":0.1274},{"x":0.6387,"y":0.1313},{"x":0.605,"y":0.1338},{"x":0.5798,"y":0.1391},{"x":0.5546,"y":0.1451},{"x":0.5294,"y":0.1522},{"x":0.5042,"y":0.1613},{"x":0.4706,"y":0.1692},{"x":0.4454,"y":0.1828},{"x":0.4034,"y":0.1935},{"x":0.3445,"y":0.1981},{"x":0.3277,"y":0.2349},{"x":0.3109,"y":0.2984},{"x":0.2605,"y":0.3735},{"x":0.1765,"y":0.5},{"x":0.0,"y":1.0}], roc: [{"x":0.0,"y":0.0},{"x":0.0013,"y":0.0336},{"x":0.0047,"y":0.0756},{"x":0.0074,"y":0.1092},{"x":0.0121,"y":0.1429},{"x":0.0134,"y":0.1765},{"x":0.0214,"y":0.2101},{"x":0.0288,"y":0.2269},{"x":0.0348,"y":0.2689},{"x":0.0543,"y":0.3025},{"x":0.0784,"y":0.3193},{"x":0.1105,"y":0.3445},{"x":0.1259,"y":0.3866},{"x":0.1353,"y":0.4034},{"x":0.1487,"y":0.4286},{"x":0.1661,"y":0.4538},{"x":0.1916,"y":0.4706},{"x":0.2063,"y":0.4958},{"x":0.2284,"y":0.521},{"x":0.2398,"y":0.5378},{"x":0.278,"y":0.563},{"x":0.2974,"y":0.5882},{"x":0.3141,"y":0.605},{"x":0.3369,"y":0.6303},{"x":0.347,"y":0.6555},{"x":0.3684,"y":0.6723},{"x":0.3985,"y":0.6975},{"x":0.426,"y":0.7227},{"x":0.4488,"y":0.7563},{"x":0.4916,"y":0.7731},{"x":0.5365,"y":0.7983},{"x":0.5472,"y":0.8235},{"x":0.6323,"y":0.8403},{"x":0.6584,"y":0.8655},{"x":0.6839,"y":0.8908},{"x":0.7046,"y":0.9076},{"x":0.7408,"y":0.9328},{"x":0.8044,"y":0.958},{"x":0.9357,"y":0.9748},{"x":1.0,"y":1.0}] },
};

export type ShapRow = { feature: string; meanAbsShap: number };
// Mean |SHAP value| for the tuned LightGBM closure model, from the Colab session.
export const SHAP_TOP12: ShapRow[] = [
  { feature: "reporting_lag_minutes", meanAbsShap: 0.50334 },
  { feature: "corridor_cause_closure_rate", meanAbsShap: 0.2876 },
  { feature: "dist_center_km", meanAbsShap: 0.28092 },
  { feature: "cause_median_ict", meanAbsShap: 0.27907 },
  { feature: "corridor_freq", meanAbsShap: 0.26813 },
  { feature: "density_2km", meanAbsShap: 0.21849 },
  { feature: "density_5km", meanAbsShap: 0.21296 },
  { feature: "same_cause_corridor_7d", meanAbsShap: 0.148 },
  { feature: "veh_type_enc", meanAbsShap: 0.12911 },
  { feature: "hour_sin", meanAbsShap: 0.12548 },
  { feature: "corridor_enc", meanAbsShap: 0.11713 },
  { feature: "cause_enc", meanAbsShap: 0.09653 },
];

// --- Task B: survival leaderboard -------------------------------------------
// Source: pasted directly from the user's Colab run (fair, repo-matched
// 60/20/20 split — see "Fair Task B comparison" section copy).
export type SurvivalRow = {
  model: string;
  family: string;
  cIndex: number;
  ibs: number | null;
  p80Coverage: number | null;
};
export const SURVIVAL_ROWS: SurvivalRow[] = [
  { model: "GradientBoostingSurvival (Cox)", family: "sksurv", cIndex: 0.6367, ibs: 0.1828, p80Coverage: 0.8962 },
  { model: "XGBoost AFT", family: "gbdt(aft)", cIndex: 0.6298, ibs: null, p80Coverage: 0.5703 },
  { model: "RandomSurvivalForest", family: "sksurv", cIndex: 0.6185, ibs: 0.2213, p80Coverage: 0.8994 },
  { model: "Cox PH (ridge 0.1) [repo-comparable]", family: "statistical", cIndex: 0.603, ibs: null, p80Coverage: 0.9457 },
  { model: "LogNormal AFT", family: "statistical(AFT)", cIndex: 0.5906, ibs: null, p80Coverage: 0.8754 },
  { model: "LogLogistic AFT", family: "statistical(AFT)", cIndex: 0.5902, ibs: null, p80Coverage: 0.8802 },
  { model: "ComponentwiseGBSurvival", family: "sksurv", cIndex: 0.5861, ibs: 0.1994, p80Coverage: 0.8994 },
  { model: "Cox PH (lasso 0.5)", family: "statistical", cIndex: 0.5855, ibs: null, p80Coverage: 0.9361 },
  { model: "Weibull AFT", family: "statistical(AFT)", cIndex: 0.5799, ibs: null, p80Coverage: 0.8898 },
  { model: "ExtraSurvivalTrees", family: "sksurv", cIndex: 0.5798, ibs: 0.2341, p80Coverage: 0.8994 },
  { model: "FastSurvivalSVM", family: "sksurv", cIndex: 0.5249, ibs: null, p80Coverage: null },
  { model: "Coxnet (elastic-net Cox)", family: "sksurv", cIndex: 0.5073, ibs: null, p80Coverage: null },
];
export const SURVIVAL_REPO_BASELINE_C_INDEX = 0.7307;
export const SURVIVAL_P80_TARGET = 78;
// From-scratch Cox PH refit on the same fair (repo-matched) split, included in
// SURVIVAL_ROWS as "Cox PH (ridge 0.1) [repo-comparable]" — pulled out here so
// prose can reference it by name without re-parsing the model label string.
export const SURVIVAL_FAIR_COX_C_INDEX =
  SURVIVAL_ROWS.find((r) => r.model.includes("repo-comparable"))?.cIndex ?? 0;

// --- Leakage-fix before/after (3-way) ---------------------------------------
// Closure PR-AUC, ROC-AUC, F1-macro and Cox C-index, computed in this session:
//   "documented"  — original readme.md baseline (separate research-notebook pipeline)
//   "modelZoo"    — best practical pick from the Colab model-zoo sweep
//   "corrected"   — backend/src/grid_unlocked/learning/training_core.py, BEFORE vs
//                   AFTER the leakage fix (whole-population priors -> expanding/
//                   past-only priors; Cox censored-duration prior-fill -> true
//                   elapsed-to-censor-time), same held-out split, same code path.
export const LEAKAGE_FIX_CLOSURE = {
  documented: { label: "Documented baseline (readme.md)", prAuc: 0.282 },
  modelZoo: { label: "Colab model-zoo best (LightGBM+SMOTE)", prAuc: 0.308 },
  productionBefore: { label: "Production — before fix (leaky priors)", prAuc: 0.394 },
  productionAfter: { label: "Production — after fix (leakage-safe)", prAuc: 0.371 },
};
export const LEAKAGE_FIX_COX = {
  documented: { label: "Documented baseline (readme.md)", cIndex: 0.7307 },
  modelZoo: { label: "Colab model-zoo best (GBSA, fair split)", cIndex: 0.6367 },
  productionBefore: { label: "Production — before fix (prior-filled censoring)", cIndex: 0.652 },
  productionAfter: { label: "Production — after fix (true censoring horizon)", cIndex: 0.575 },
};
