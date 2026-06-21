"""M12 — TransitImpactService.

Overlays mock BMTC schedule/AVL data with M03 predicted corridor delay to
produce a micro-transit passenger-delay index for command briefings.
Advisory only — never controls bus dispatch or routing.

Deferred to Phase 2:
  - D-M12-01: Live BMTC GTFS-RT instead of MockGtfsClient
  - D-M12-02: Real route polyline / corridor-buffer spatial join instead of
    a hardcoded corridor -> route map
  - D-M12-03: Real transfer_overload_risk formula (needs transfer-hub +
    headway data not present in this codebase)
  - D-M12-04: Wiring into M09 ActionCard / M15 dashboard panel
"""
