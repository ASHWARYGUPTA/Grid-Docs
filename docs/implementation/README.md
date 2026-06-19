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
| [AUDIT.md](AUDIT.md) | M01 + M02 audit | SOLID / PRD alignment review |

**Spec references (target contracts):**

- [../IMPLEMENTATION_MODULES.md](../IMPLEMENTATION_MODULES.md) — full module PRD
- [../ML_MODELS_PRD.md](../ML_MODELS_PRD.md) — ML feature allowlists
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — system design
- [../TECH_STACK.md](../TECH_STACK.md) — stack and Docker setup

**Backend entrypoint:** `backend/src/grid_unlocked/main.py` (FastAPI v0.9.0)

**Run locally:**

```bash
docker compose up --build          # Postgres + Redis + API
cd backend && uv run pytest        # 116 tests (M01–M09 incl. requirements gates)
```
