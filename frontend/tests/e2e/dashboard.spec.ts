import { test, expect } from "@playwright/test";

// Helpers are inlined rather than imported from a sibling module — relative
// imports between spec files trip a Node 22 ESM-loader resolve-hook bug in
// this Playwright version (`context.conditions?.includes is not a
// function`), so each spec stays self-contained.
const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8100";

// `corridor` must be one of ingestion/vocab.py's VALID_CORRIDORS — anything
// else is normalized to null server-side (M01 normalizer), so each test uses
// a distinct real corridor to keep its queue row unambiguous.
function eventPayload(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    event_type: "unplanned",
    latitude: 12.969,
    longitude: 77.701,
    event_cause: "accident",
    requires_road_closure: true,
    start_datetime: "2024-03-07T12:00:00+00:00",
    status: "active",
    authenticated: "yes",
    created_date: "2024-03-07T12:05:00+00:00",
    corridor: "ORR East 1",
    priority: "High",
    veh_type: "heavy_vehicle",
    ...overrides,
  };
}

test.describe.configure({ mode: "serial" });

// ClientShell (components/client-shell.tsx) redirects any unauthenticated
// visit to non-public routes (e.g. /live) to /login — added after this spec
// was written, so every test must seed a session before navigating. Auth is
// purely client-side (lib/auth.ts reads localStorage synchronously on
// mount), so an addInitScript that writes the session before any page JS
// runs is the correct bypass — no UI login flow needed per test.
//
// The first-login onboarding tour (components/onboarding-tour.tsx) also
// postdates this spec: it renders a full-screen backdrop (z-[9999]) that
// intercepts pointer events on every element behind it, so a click in a
// fresh session hangs retrying instead of failing fast. Pre-marking the
// tour complete for the seeded user avoids that without weakening what the
// test is actually asserting.
const COMMANDER_EMAIL = "commander@gridunlocked.in";

test.beforeEach(async ({ page }) => {
  await page.addInitScript((email) => {
    window.localStorage.setItem(
      "gridunlocked_session",
      JSON.stringify({ email, name: "Traffic Commander", role: "commander" })
    );
    window.localStorage.setItem(`gridunlocked_tour_${email}`, "done");
  }, COMMANDER_EMAIL);
});

test("new event appears as a map pin and action card within 5s", async ({ page, request }) => {
  await page.goto("/live");
  // Give the dashboard WebSocket time to finish its handshake before
  // ingesting, so the 5s budget below measures the spec's actual contract
  // (ingest -> delta -> UI update) rather than connection setup time.
  await page.waitForTimeout(500);

  const t0 = Date.now();
  await request.post(`${API_URL}/ingest/astram`, {
    data: eventPayload("E2E0001", { corridor: "CBD 1" }),
  });

  await expect(page.getByText("CBD 1").first()).toBeVisible({ timeout: 5000 });
  expect(Date.now() - t0).toBeLessThan(5000);

  await page.getByText("CBD 1").first().click();
  await expect(page.getByText("E2E0001").first()).toBeVisible({ timeout: 5000 });
});

test("shadow mode disables approve button with an explanation", async ({ page, request }) => {
  await page.goto("/live");
  await request.post(`${API_URL}/ingest/astram`, {
    data: eventPayload("E2E0002", { corridor: "CBD 2" }),
  });
  await expect(page.getByText("CBD 2").first()).toBeVisible({ timeout: 8000 });
  await page.getByText("CBD 2").first().click();
  await expect(page.getByText("E2E0002").first()).toBeVisible({ timeout: 8000 });

  const approveBtn = page.getByRole("button", { name: "Approve" });
  await expect(approveBtn).toBeDisabled();
  await page.locator('[data-slot="tooltip-trigger"]').filter({ hasText: "Approve" }).hover();
  await expect(page.getByText(/shadow mode active/i)).toBeVisible({ timeout: 5000 });
});

test("forcing tier 3 shows the manual-mode banner and audit-only behavior", async ({
  page,
  request,
}) => {
  await request.post(`${API_URL}/governance/override-tier`, {
    data: { tier: "3", reason: "e2e test", operator_id: "E2E-OPERATOR" },
  });
  await request.post(`${API_URL}/ingest/astram`, {
    data: eventPayload("E2E0003", { corridor: "Tumkur Road" }),
  });

  await page.goto("/live");
  await expect(page.getByText("Tumkur Road").first()).toBeVisible({ timeout: 8000 });
  await page.getByText("Tumkur Road").first().click();
  await expect(page.getByText("E2E0003").first()).toBeVisible({ timeout: 8000 });
  await expect(page.getByText(/Tier 3 — continuity SOP mode/i)).toBeVisible();

  // restore tier 1 so later tests in this file aren't affected
  await request.post(`${API_URL}/governance/override-tier`, {
    data: { tier: "1", reason: "e2e cleanup", operator_id: "E2E-OPERATOR" },
  });
});

test("websocket reconnects and resumes receiving deltas without a full page reload", async ({
  page,
  request,
}) => {
  await page.goto("/live");
  await request.post(`${API_URL}/ingest/astram`, {
    data: eventPayload("E2E0004", { corridor: "Varthur Road" }),
  });
  await expect(page.getByText("Varthur Road").first()).toBeVisible({ timeout: 8000 });

  // Drop the network briefly to force the live WebSocket closed; useDashboardSocket's
  // backoff loop should reconnect once connectivity returns, with no page reload.
  await page.context().setOffline(true);
  await page.waitForTimeout(1000);
  await page.context().setOffline(false);

  await request.post(`${API_URL}/ingest/astram`, {
    data: eventPayload("E2E0005", { corridor: "Magadi Road" }),
  });
  await expect(page.getByText("Magadi Road").first()).toBeVisible({ timeout: 20_000 });
});

test("newly ingested event appears in the real-time incident feed the map pin layer consumes", async ({
  request,
}) => {
  // MapPanel's incident pins come from GET /api/v1/incidents/active — this
  // environment has no NEXT_PUBLIC_MAPPLS_KEY configured (see map-panel.tsx's
  // fallback), so a DOM-level marker assertion isn't possible here. This
  // instead verifies the real data contract the pin layer renders from: a
  // freshly ingested event shows up as active with its real coordinates and
  // status, which is what MapPanel's refreshIncidents() fetches and diffs by
  // event_id.
  await request.post(`${API_URL}/ingest/astram`, {
    data: eventPayload("E2E0006", { corridor: "Hosur Road", latitude: 12.91, longitude: 77.64 }),
  });

  await expect
    .poll(
      async () => {
        const res = await request.get(`${API_URL}/api/v1/incidents/active?limit=200`);
        const body = await res.json();
        return body.incidents.find((i: { event_id: string }) => i.event_id === "E2E0006");
      },
      { timeout: 8000 }
    )
    .toMatchObject({
      event_id: "E2E0006",
      corridor: "Hosur Road",
      lat: 12.91,
      lng: 77.64,
      status: "active",
    });
});

test("websocket emits an incident-scoped delta when a new event is ingested", async ({
  page,
  request,
}) => {
  // Confirms the A-2 contract end-to-end: useDashboardSocket's lastDelta
  // surfaces scope:"incident" (not just the pre-existing "hotspot" delta)
  // for a fresh ingest. The page doesn't need to render anything from this
  // delta for the test to be meaningful — it's asserting the wire contract
  // MapPanel's incident-refresh effect depends on.
  await page.goto("/live");
  await page.waitForTimeout(500);

  const wsUrl = `${API_URL.replace(/^http/, "ws")}/ws/dashboard`;
  const deltaScopesPromise = page.evaluate((url) => {
    return new Promise<string[]>((resolve) => {
      const scopes: string[] = [];
      const ws = new WebSocket(url);
      ws.onmessage = (event) => {
        const delta = JSON.parse(event.data);
        scopes.push(delta.scope);
        if (scopes.includes("incident")) {
          ws.close();
          resolve(scopes);
        }
      };
      setTimeout(() => {
        ws.close();
        resolve(scopes);
      }, 6000);
    });
  }, wsUrl);

  await page.waitForTimeout(300);
  await request.post(`${API_URL}/ingest/astram`, {
    data: eventPayload("E2E0007", { corridor: "Bannerghata Road" }),
  });

  const scopes = await deltaScopesPromise;
  expect(scopes).toContain("incident");
});
