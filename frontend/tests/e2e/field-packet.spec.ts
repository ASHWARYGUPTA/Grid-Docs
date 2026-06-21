import { test, expect } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8100";

function eventPayload(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    event_type: "unplanned",
    latitude: 12.969,
    longitude: 77.701,
    event_cause: "accident",
    requires_road_closure: true,
    start_datetime: "2024-03-07T16:00:00+00:00",
    status: "active",
    authenticated: "yes",
    created_date: "2024-03-07T16:05:00+00:00",
    corridor: "ORR East 1",
    priority: "High",
    veh_type: "heavy_vehicle",
    ...overrides,
  };
}

test("field packet renders and the closure form submits successfully", async ({ page, request }) => {
  const eventId = "E2EFIELD0001";
  await request.post(`${API_URL}/ingest/astram`, { data: eventPayload(eventId) });
  await page.waitForTimeout(500);

  const recommendResp = await request.post(`${API_URL}/dispatch/recommend`, {
    data: { event_id: eventId, force_greedy: true },
  });
  expect(recommendResp.ok()).toBeTruthy();
  const { recommendation_id } = await recommendResp.json();

  await page.goto(`/field/${recommendation_id}`);

  await expect(page.getByText(recommendation_id)).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("Incident clearance time")).toBeVisible();

  await page.getByLabel("Barricades used").fill("2");
  await page.getByLabel("Officers used").fill("3");
  await page.getByRole("button", { name: "Close event" }).click();

  await expect(page.getByText("Closure recorded")).toBeVisible({ timeout: 8000 });
});
