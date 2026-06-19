# M09 — RecommendationAPI (Implementation Record)

**Version:** 0.9  
**Backend path:** `backend/src/grid_unlocked/recommendations/`  
**Status:** Implemented (MVP)  
**Spec reference:** [IMPLEMENTATION_MODULES.md § M09](../IMPLEMENTATION_MODULES.md)

---

## Purpose

M09 is the **human-in-the-loop facade** that assembles M03–M08 outputs into a unified **ActionCard** with evidence, provenance, and an approval workflow. It gates M10/M11 actuation behind commander approval and respects M14 governance (tier + shadow mode).

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/recommendations/queue?severity=` | Prioritized alert queue (RCI descending) |
| GET | `/recommendations/{event_id}?mode=&refresh=` | Full or skeleton action card |
| POST | `/recommendations/{event_id}/refresh` | Force recompute |
| POST | `/recommendations/{card_id}/approve` | Commander approval (M10 stub when shadow off) |
| POST | `/recommendations/{card_id}/reject` | Rejection with reason code |

### Card modes

| Mode | Behavior |
|---|---|
| `skeleton` | Impact + propagation + diversions; dispatch pending |
| `complete` | Full card including M07 dispatch section |
| `auto` | Same as complete (MVP) |

---

## ActionCard sections

| Section | Source module |
|---|---|
| `impact` | M03 — RCI, p_closure, severity band |
| `propagation` | M04 — cascade summary |
| `hotspot_context` | M05 — nearby clusters, cell history |
| `diversions` | M08 — top-k scenario routes |
| `dispatch` | M07 — assignments + provenance |
| `planned` | M06 — barricade/staffing (planned events only) |
| `evidence` | M03 explain + model versions + diversion ranks |
| `governance` | M14 stub — tier, shadow_mode, manual_mode |

---

## Core behavior

### Card assembly

1. Check cache (`action_cards`) unless `refresh=true`
2. Load event from M01/M02; 404 if missing
3. Tier 3 / manual mode → SOP fallback card (no dispatch)
4. Parallel orchestration: M03 score + explain, M04 ripple, M05 hotspot context, M08 scenarios
5. Skeleton timing recorded at `skeleton_ms`; dispatch appended for complete mode
6. Persist card; return

### Alert prioritization

- **CRITICAL:** p_closure > 0.7 AND named corridor AND peak hour
- **HIGH:** Orange/Red severity OR rci ≥ 0.55
- **MEDIUM:** Yellow OR rci ≥ 0.35
- **LOW:** otherwise

### Approval workflow

- `shadow_mode=true` (default): approve logs only; `execution_enqueued=false`
- `shadow_mode=false`: M10 stub enqueue (Phase 1.5)
- Reject captures `reason_code` + notes in `approval_records`

---

## Integration

| Module | Usage |
|---|---|
| M03 | Impact score + SHAP explain |
| M04 | Propagation ripple |
| M05 | Hotspot cell context |
| M06 | Planned package section |
| M07 | Dispatch recommendation |
| M08 | Diversion scenarios |
| M14 | Governance tier + shadow flag (config stub) |
| M10/M11 | Post-approval actuation (stubbed) |
| M15/M16 | Dashboard + field packet deep link |

---

## Source files

| File | Responsibility |
|---|---|
| `router.py` | FastAPI routes |
| `service.py` | Card assembly, approve/reject, queue |
| `repository.py` | `action_cards` + `approval_records` persistence |
| `governance.py` | M14 config stub |
| `schemas.py` | ActionCard, ApprovalResult contracts |

---

## Database

### `action_cards`

| Column | Notes |
|---|---|
| `card_id` | PK (`CARD-…`) |
| `event_id` | FK to normalized event |
| `status` | partial / complete / approved / rejected |
| `card_json` | Full `ActionCard` snapshot |
| `created_at`, `updated_at` | Audit timestamps |

### `approval_records`

| Column | Notes |
|---|---|
| `record_id` | PK |
| `card_id` | FK |
| `commander_id` | Approver identity |
| `action` | approve / reject |
| `reason_code`, `notes` | Rejection metadata |
| `shadow_mode` | Whether actuation was suppressed |
| `created_at` | Immutable timestamp |

---

## Configuration (`GRID_*` env)

| Setting | Default | Meaning |
|---|---|---|
| `governance_tier` | `1` | 1=MILP, 2=greedy, 3=SOP |
| `governance_shadow_mode` | `true` | Suppress M10 on approve |
| `recommendation_skeleton_sla_ms` | 350 | Skeleton SLA target |
| `recommendation_complete_sla_ms` | 1800 | Complete card SLA (dispatch-bound) |

---

## Tests

| File | Count | Coverage |
|---|---|---|
| `test_recommendations.py` | 7 | Unit/API: complete, skeleton, approve, reject, queue, refresh, 404 |
| `test_integration.py` | +2 | M09 in full pipeline + planned + lifecycle |
| `test_robustness.py` | +4 | Cache, skeleton, 404, burst |

---

## Demo curl

```bash
# Ingest incident
curl -X POST http://localhost:8000/ingest/astram -H 'Content-Type: application/json' -d '{
  "id": "FKIDREC-DEMO",
  "event_type": "unplanned",
  "latitude": 12.969, "longitude": 77.701,
  "event_cause": "accident", "corridor": "ORR East 1",
  "start_datetime": "2024-03-07T16:00:00+00:00",
  "status": "active", "authenticated": "yes",
  "veh_type": "heavy_vehicle", "priority": "High"
}'

# Wait ~0.3s for M02 features, then fetch action card
curl "http://localhost:8000/recommendations/FKIDREC-DEMO?mode=complete&refresh=true"

# Shadow approve (no M10 execution)
curl -X POST "http://localhost:8000/recommendations/CARD-XXXX/approve" \
  -H 'Content-Type: application/json' \
  -d '{"commander_id": "CMD-001", "override_codes": []}'
```

---

## Known limitations (MVP)

- No WebSocket `recommendation.updated` push (M15 Phase 1.5)
- M14 governance is config stub, not live console
- M10/M11 execution stubbed; approve logs only in shadow mode
- Tier 3 SOP card uses static priors, not live M03
- Queue reads cached cards; events without cards omitted until first GET

---

## Next

- **M10** AgenticExecutionBroker — real post-approval station dispatch
- **M14** GovernanceConsole — live tier/shadow API replacing config stub
- **M15** CommandDashboard — WebSocket card updates
