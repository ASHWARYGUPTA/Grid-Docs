# Implementation Documentation

Engineering records for **built** Grid Unlocked backend modules. These docs describe what is actually in the codebase — not the full target spec.

| Document | Module | Status |
|---|---|---|
| [M01_IngestionGateway.md](M01_IngestionGateway.md) | M01 — Ingestion | Implemented (v0.1) |
| [M02_FeatureGraphService.md](M02_FeatureGraphService.md) | M02 — Features | Implemented (v0.2) |
| [M03_ImpactEngine.md](M03_ImpactEngine.md) | M03 — Impact scoring | Implemented (v0.3) |
| [M04_PropagationEngine.md](M04_PropagationEngine.md) | M04 — GCDH propagation | Implemented (v0.4) |
| [M05_HotspotService.md](M05_HotspotService.md) | M05 — Hotspots | Implemented (v0.5) |
| [M06_PlannedEventTemplateEngine.md](M06_PlannedEventTemplateEngine.md) | M06 — Planned packages | Implemented (v0.6) |
| [M07_DispatchOrchestrator.md](M07_DispatchOrchestrator.md) | M07 — Dispatch MILP+Greedy | Implemented (v0.7) |
| [M08_DiversionRoutingEngine.md](M08_DiversionRoutingEngine.md) | M08 — Diversion atlas + k-shortest | Implemented (v0.8) |
| [M09_RecommendationAPI.md](M09_RecommendationAPI.md) | M09 — Action card facade + approval | Implemented (v0.9) |
| [M10_AgenticExecutionBroker.md](M10_AgenticExecutionBroker.md) | M10 — Post-approval dispatch + barricade execution broker | Implemented (v1.0, stubbed station APIs) |
| [M11_VMSRouter.md](M11_VMSRouter.md) | M11 — Diversion-to-board template engine + VMS fanout | Implemented (v1.0, stubbed webhook vendor) |
| [M12_TransitImpactService.md](M12_TransitImpactService.md) | M12 — BMTC passenger-delay index, advisory only | Implemented (v1.0, stubbed mock GTFS-RT + static route map per spec) |
| [M13_ReplayLearningService.md](M13_ReplayLearningService.md) | M13 — 80/20 replay buffer, retrain, 94% gate + anchor regression check | Implemented (v1.0, synchronous in-request, no MLflow/scheduler) |
| [M14_GovernanceConsole.md](M14_GovernanceConsole.md) | M14 — Tier/shadow control, health rollup, auto-transitions, drills | Implemented (v1.0, promotion checklist now reads real M13 eval data) |
| [M15_CommandDashboard.md](M15_CommandDashboard.md) | M15 — Primary TMC UI: Next.js dashboard + WebSocket fanout | Implemented (v1.0, citizen triage placeholder pending M17) |
| [M16_FieldOfficerApp.md](M16_FieldOfficerApp.md) | M16 — Field officer packet, ack, closure capture with resource labels | Implemented (v1.0, localStorage offline queue, no Service Worker) |
| [M17_CitizenReportService.md](M17_CitizenReportService.md) | M17 — Citizen photo+GPS report, ICT quote, verify/reject, corridor pre-alerts | Implemented (v1.0, DB-stored photos, polling-based pre-alerts) |
| [M18_CitizenApp.md](M18_CitizenApp.md) | M18 — Commuter report form, ICT quote display, corridor subscriptions, pre-alert toasts | Implemented (v1.0, frontend-only, no nearby-hotspots proxy or rate limiting) |
| [AUDIT.md](AUDIT.md) | M01 + M02 audit | SOLID / PRD alignment review |

**Spec references (target contracts):**

- [../IMPLEMENTATION_MODULES.md](../IMPLEMENTATION_MODULES.md) — full module PRD
- [../ML_MODELS_PRD.md](../ML_MODELS_PRD.md) — ML feature allowlists
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — system design
- [../TECH_STACK.md](../TECH_STACK.md) — stack and Docker setup

**Backend entrypoint:** `backend/src/grid_unlocked/main.py` (FastAPI v1.0.0)

**Run locally:**

```bash
docker compose up --build          # Postgres + Redis + API + frontend (waits for API health)
cd backend && uv run pytest        # 216 tests (M01–M18 incl. requirements gates; M18 is frontend-only)
cd frontend && pnpm test:unit      # 33 Vitest unit tests (incl. M16, M18)
cd frontend && pnpm build && pnpm start &   # production build required for E2E
cd frontend && pnpm test:e2e       # Playwright E2E against the production build
```
