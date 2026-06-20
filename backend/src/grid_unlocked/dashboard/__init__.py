"""M15 — CommandDashboard.

Owns the WebSocket fanout that pushes live deltas (action card changes,
governance tier changes, hotspot updates) to connected dashboard clients.
REST data for the dashboard's panels is served directly by M05/M06/M08/M09/
M13/M14 — this module only adds the push transport on top.

Deferred to Phase 1.5:
  - D-M15-02: in-process pub/sub (mirrors ingestion/bus.py::InProcessEventBus),
    not Redis pub/sub — same precedent as M01's event bus.
"""
