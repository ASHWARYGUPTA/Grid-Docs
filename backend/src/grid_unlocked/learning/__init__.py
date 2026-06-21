"""M13 — ReplayLearningService.

Builds 80/20 replay buffers (recent-closed + stratified historical anchor),
retrains M03's closure classifier (LightGBM) and ICT survival model
(Cox PH), evaluates against a 94% accuracy gate with anti-catastrophic-
forgetting anchor-regression protection, and stages/promotes model versions
that M14's GovernanceConsole gates on for production sign-off.

Deferred to Phase 1.5:
  - D-M13-01: No MLflow — joblib + metadata.json sidecar, same convention M03
    already uses. New model versions land in models/v2, v3, ... ; v1 is never
    overwritten.
  - D-M13-02: Retrain runs synchronously in-request, not an async job/DAG —
    no task queue exists in the repo; full-corpus retrain measured at ~3.3s.
  - D-M13-03: trigger=scheduled|drift is accepted and recorded but not
    auto-fired — no scheduler/drift-monitor infra exists (same precedent as
    M14's on-demand-only cascade drills).
"""
