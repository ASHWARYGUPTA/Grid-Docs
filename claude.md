# claude.md — Grid Unlocked (Gridlock 2.0)

This file is the Claude Code briefing for the **awesome-napier-d93c60** worktree. The full v2 plan lives in `C:\Users\Acer\Downloads\Grid_Unlocked_Build_Guide.md` (a.k.a. Grid Unlocked Codebase-Grounded Build Guide).

---

## 1. Project at a glance

- **What it is.** An intelligence layer on top of ASTraM (real Bengaluru traffic data) — backend M01–M18 already implemented, frontend Next 16 / React 19 / Mappls already implemented. This branch is a **refactor + extension**, not a build-from-scratch.
- **Three concurrent streams**: A — Backend / Data APIs (Python), B — Live Map & Real-Time (frontend), C — Workflows & Closed-Loop (frontend).
- **My stream is A.** I touch Python only: `backend/src/grid_unlocked/**`, `backend/scripts/**`, `backend/tests/**`. Streams B and C own the frontend.

## 2. Non-negotiables

- **Real data only.** Every number/pin/route on screen must trace to a real endpoint backed by ASTraM data or a real model. Never fabricate coordinates or scores. If a corridor proxy node has no centroid, omit it — don't synthesize.
- **Use existing infrastructure.** The ingest fan-in (`event_bus`) and dashboard fan-out (`dashboard_bus` → `/ws/dashboard`, `DashboardDelta` schema) already exist. Add scopes; don't build a new socket.
- **The five pitfalls (P1–P5).** They are real; I have hit them before:
  1. *Next 16 / React 19 / Tailwind 4 are not "just Next.js"* — frontend stream concern, but be aware.
  2. **`get_session`, not `get_db`.** Models are `…Row` (e.g. `NormalizedEventRow`). RCI lives in `impact_scores`, **not** on the event. Event timestamp is `ingested_at` (no `created_at` column on `normalized_events`).
  3. **Status vocab is lowercase**: `active` / `closed` / `resolved`. Filtering on `"ACTIVE"` matches zero rows.
  4. **ICT is in hours** (`ict_p50_h`). Conversion happens at the UI edge, never server-side.
  5. **Don't build a second WebSocket or `ConnectionManager`.** Don't add a `ReplayBufferEntry` table.

## 3. Stream A scope (this branch)

| ID | Status | Summary |
|----|--------|---------|
| A-1 | ✅ done | `GET /api/v1/incidents/active` — `NormalizedEventRow(status='active')` ⨝ latest `ImpactScoreRow`. |
| A-2 | ✅ done | `DeltaScope.INCIDENT` + `dashboard/incident_subscriber.py` fan-out on ingest. |
| A-3 | ✅ done | `DiversionRoute.waypoints` (corridor centroids); `RouteWaypoint` now `{lat, lng, corridor}`. |
| A-4 | ✅ done | `GET /api/v1/corridors` — real centroids from `corridor_centroids`. |
| A-5 (bonus) | ✅ done | `PropagationNode` gains `lat`/`lng` (resolved via centroids; `null` when unresolved). |
| A-6 | ✅ done | `backend/scripts/seed_demo.py` — 20 canonical-vocab events. |
| A-7 | ✅ done | `tests/test_maps.py`, `tests/test_incident_broadcast.py`, extended `tests/test_diversions.py`. |

## 4. Files I am allowed to touch

- `backend/src/grid_unlocked/maps/**` (created)
- `backend/src/grid_unlocked/dashboard/{schemas,incident_subscriber}.py`
- `backend/src/grid_unlocked/diversions/{schemas,service,router}.py`
- `backend/src/grid_unlocked/propagation/{schemas,service}.py`
- `backend/src/grid_unlocked/main.py` (register new router + subscriber only)
- `backend/scripts/seed_demo.py`
- `backend/tests/test_maps.py`, `tests/test_incident_broadcast.py`, `tests/test_diversions.py`
- This file (`claude.md`)

Frontend (`frontend/**`) is **not mine** — Streams B and C own it.

## 5. Shared contract surface (frozen)

The contract Stream B and C build against — keep these shapes stable.

```ts
// Frontend mirror (Stream B/C own the edit to lib/types.ts):
type DeltaScope = "card" | "tier" | "hotspot" | "citizen" | "field" | "incident";

interface ActiveIncident {
  event_id: string; corridor: string | null; junction: string | null;
  event_type: string; event_cause: string; lat: number; lng: number;
  rci: number | null; p_closure: number | null;
  severity_band: string | null; status: string; ingested_at: string;
}
interface ActiveIncidentsResponse { incidents: ActiveIncident[] }

interface RouteWaypoint { lat: number; lng: number; corridor: string | null }
// DiversionRoute gains: waypoints: RouteWaypoint[]

interface CorridorCentroid { name: string; lat: number; lon: number; sample_count: number }
interface CorridorsResponse { corridors: CorridorCentroid[] }
```

Endpoints I now expose:

- `GET /api/v1/incidents/active?limit=100` (≤500)
- `GET /api/v1/corridors`
- `GET /diversions/scenarios/{event_id}` → each route now carries `waypoints[]`
- `GET /diversions/atlas/{junction_id}` + `POST /diversions/compute` → same waypoint enrichment
- `GET /propagation/active` → each node carries optional `lat`/`lng`
- `WS /ws/dashboard` → new scope `incident` (lightweight payload, fired from ingest subscriber)

## 6. Conventions I follow inside this codebase

- **DI**: `from grid_unlocked.db.session import get_session` (async generator) — used in `Depends(get_session)` and in service constructors via `AsyncSession`.
- **Models**: SQLAlchemy 2.0 declarative rows under `grid_unlocked.db.models`. Names end in `…Row`.
- **Schemas**: Pydantic v2; field names match the frontend contract (snake_case server-side, no aliasing unless the doc specifies it).
- **Subscribers**: register once at module-load time via a `_registered` flag; wire into `lifespan()` in `main.py`. Errors must be caught + logged so fan-out never breaks ingest.
- **Vocab** (`grid_unlocked.ingestion.vocab`): 22 corridors, 17 snake_case causes, lowercase status, bbox `lat [12.8, 13.3] lon [77.3, 77.8]`.

## 7. Dev / test commands

```powershell
# uv cache on Windows occasionally locks (Defender scan); use a fresh cache dir:
$env:UV_CACHE_DIR = "$env:TEMP\uv-cache-altA"

# From backend/:
uv sync                                    # install deps
uv run python scripts/seed_demo.py         # 20 synthetic events to /ingest/astram
uv run pytest -q                            # run all tests
uv run pytest tests/test_maps.py -q         # just my new tests
```

### Known test-suite caveat (pre-existing, not mine)
`tests/test_dashboard.py` fails on its own (`no such table: corridor_cause_priors` — the StarletteDeprecationWarning's TestClient/lifespan path doesn't share the conftest in-memory SQLite across event loops). This was already broken before this branch. I worked around it by writing `tests/test_incident_broadcast.py` as a direct event-bus/dashboard-bus unit test, not a TestClient WebSocket test. If/when the upstream pattern is fixed, both can be migrated.

## 8. Do-not list (Stream A scope)

- ✗ Don't add a hardcoded gutter-points / bottleneck list — real M05 hotspots already cover it.
- ✗ Don't add `osmnx` / `geojson` / `maplibre` — not needed for any A endpoint.
- ✗ Don't fabricate coordinates. Incidents have real lat/lng; corridor geometry comes from `corridor_centroids`.
- ✗ Don't write a parallel close endpoint — M16 `POST /field/close/{event_id}` already feeds the M13 buffer.
- ✗ Don't `REFRESH MATERIALIZED VIEW active_events` — no such view exists in this repo.

## 9. Git workflow

- Branch: `claude/awesome-napier-d93c60`.
- Commit per logical chunk; push after each commit (user preference).
- Commit-message style: `A-N: short summary` body; trailer `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.

## 10. References

- Full guide: `C:\Users\Acer\Downloads\Grid_Unlocked_Build_Guide.md`
- Frontend agents brief: `frontend/AGENTS.md`
- Reality vs. original docx delta: Appendix B of the build guide.
