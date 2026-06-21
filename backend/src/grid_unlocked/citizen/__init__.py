"""M17 — CitizenReportService.

Photo+GPS citizen reports: location snap (device GPS, EXIF fallback), H3/corridor
join, keyword cause-hint, immediate ICT quote (M03 live or corridor×cause prior
fallback), triage forward to M01 as authenticated=false, and commander
verify/reject before M09 dispatch is enabled. Corridor subscriptions feed a
polling-based pre-alert matcher against M05 hotspots and M04 propagation state.

Deferred to Phase 2:
  - Vision-only geolocation without GPS/EXIF.
  - Real S3-compatible photo storage (MVP stores photo bytes in the DB row).
  - Push-based (vs polling) pre-alert triggers from M04/M05.
"""
