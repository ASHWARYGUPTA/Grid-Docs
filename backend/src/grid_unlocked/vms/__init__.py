"""M11 — VMSRouter.

Converts M08 diversion routes to board-friendly text and fans out to
VMS/LED board webhook endpoints (mock in hackathon phase).

Deferred to Phase 1.5:
  - D-M11-01: Live VMS webhook delivery to real LED/VMS board endpoints
  - D-M11-02: Kannada/English bilingual template engine
  - D-M11-03: VMS board registry DB table with real BTP board data
  - D-M11-04: Commander-specified board_ids via ApproveRequest extension
  - D-M11-06: M10 ACK → M11 sequential trigger instead of parallel
  - D-M11-07: Per-board delivery latency metrics for M14 health dashboard
"""
