"""M14 — GovernanceConsole.

Owns tier (1/2/3), shadow mode, health rollup across M01/M02/M03/M07/M10/M11,
automatic tier transitions with recovery hysteresis, manual override audit,
cascade drills, and the M13 promotion checklist gate.

Deferred to Phase 1.5:
  - D-M14-02: RBAC / operator identity is a plain string field, not backed
    by an IAM (explicitly out of scope per spec).
  - D-M14-03: Health probe cycle runs as an in-process asyncio task (30s),
    not a separately deployable health-check service.

shadow_mode_stability (one of three promotion checklist items) remains
intentionally stubbed — it is M14's own contract per spec, not M13's.
Promotion checklist's other two items (accuracy_gate_94pct, anchor_slice_stable)
now read real eval data from M13 — see grid_unlocked.learning.
"""
