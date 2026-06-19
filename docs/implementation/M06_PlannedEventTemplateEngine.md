# M06 — PlannedEventTemplateEngine (Implementation Record)

**Version:** 0.6  
**Backend path:** `backend/src/grid_unlocked/planned/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M06](../IMPLEMENTATION_MODULES.md) · [ML_MODULES_IMPLEMENTATION.md § M06](../ML_MODULES_IMPLEMENTATION.md)

---

## Purpose

M06 generates **24–72 hour planned event packages** for coordinators: staffing ranges, barricade counts, compliance checklists, historical analog events, diversion references, and a one-time M03 impact overlay.

Planned events are 5.7% of ASTraM volume but **36.2% closure rate** — pre-packaging avoids repeated runtime M03 inference on dashboard polls.

---

## What is implemented

### API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/planned/package` | Generate or return cached `PlannedEventPackage` |
| GET | `/planned/upcoming?hours=72` | Timeline packages for active planned events |
| GET | `/templates/{cause}` | Raw template definition for MVP cause |

### PlannedEventPackage outputs

| Field | Description |
|---|---|
| `template_id` | Matched template identifier |
| `staffing_min/max` | Rule-based officer range |
| `barricade_count` | From barricade matrix (+ VIP floor) |
| `barricade_staging_required` | VIP hard rule or p_closure ≥ 0.35 |
| `deployment_lead_time_hours` | Cause-specific lead time |
| `checklist[]` | Compliance + ops items |
| `analog_events[]` | Top-3 historical planned events (CSV) |
| `diversion_refs[]` | Top-3 routes (M08 stub) |
| `impact_overlay` | One-time M03 scores cached in package |
| `cached` | True on attribute-stable re-read |

---

## Algorithms

### Template matching

Nearest-neighbor score on `(cause, corridor, dow, hour_bin, duration_class)` against pre-indexed seeds for:

- `construction` (Mysore Road weekend + generic)
- `vip_movement`
- `procession`
- `public_event`
- `protest`

### Staffing & barricades

| Cause | Officers | Barricades |
|---|---|---|
| construction | 3–8 | 6–8 (dual carriageway full = 8) |
| vip_movement | 8–20 | ≥12 (hard rule) |
| procession | 6–15 | 8 |
| public_event | 4–12 | 6 |
| protest | 6–15 | 10 |

### M03 routing (critical)

- M03 called **once** at package generation via `registry.score()`
- Cached package served when `attributes_hash` unchanged (`force_refresh=false`)
- Dashboard polls should read `impact_overlay` — **not** re-invoke `/impact/score`

### M08 diversion stub

Top-3 junction routes per corridor until M08 DiversionRoutingEngine ships.

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes |
| `service.py` | Package orchestration, M03 overlay, cache |
| `templates.py` | Pre-indexed template seeds + matcher |
| `analogs.py` | Historical analog retrieval from CSV |
| `diversion_stub.py` | M08 placeholder atlas |
| `rules.py` | VIP barricade floor, staging rules |
| `repository.py` | `planned_packages` persistence |

---

## Database

### `planned_packages`

| Column | Notes |
|---|---|
| `event_id` | PK — planned event |
| `template_id` | Matched template |
| `attributes_hash` | Invalidates cache on material change |
| `package_json` | Full serialized package |
| `generated_at` | UTC timestamp |

---

## Integration flow

```
M01 planned ingest → normalized_events (is_planned=true)
                              ↓
              POST /planned/package
                              ↓
        template match + analogs + M08 stub
                              ↓
           M03 registry.score (once)
                              ↓
              planned_packages cache
                              ↓
                    M09 / M15 timeline
```

---

## Tests

`backend/tests/test_planned.py` — 7 tests:

- Construction package with checklist, analogs, diversions
- VIP barricade staging hard rule (≥12 barricades)
- Cached re-read (`cached=true`)
- All 5 MVP template endpoints
- Construction Mysore Road analog retrieval
- Upcoming 72h timeline
- Unplanned event rejected (422)

Run: `cd backend && uv run pytest`

---

## Deferred (not blocking MVP)

| Item | Target |
|---|---|
| M08 live diversion atlas | M08 DiversionRoutingEngine |
| BBMP permit integration | Phase 2 |
| Background package pre-generation on ingest | Optional subscriber |
| `planned_templates` DB table | In-memory seeds sufficient for hackathon |
| Resource reservation (M10) | Phase 1.5 |

---

## Version history

| Version | Change |
|---|---|
| 0.6.0 | M06 PlannedEventTemplateEngine — package/upcoming/templates, M03 overlay cache |

**Next module:** M07 DispatchOrchestrator — MILP + greedy fallback with RCI/CascadeRisk inputs.
