import { test } from "@playwright/test";

test("fresh verification of all click interactions", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

  await page.goto("http://localhost:3000/live", { waitUntil: "networkidle" });
  await page.waitForTimeout(8000);
  await page.screenshot({ path: "/tmp/v3_initial.png" });
  console.log("errors after load:", JSON.stringify(errors));

  // Test 1: queue row click
  const rows = page.locator("table tbody tr");
  await rows.nth(1).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: "/tmp/v3_queue_click.png" });

  // Test 2: predicted list click
  await page.getByRole("button", { name: "Predicted" }).click();
  await page.waitForTimeout(1500);
  const bannerghata = page.locator("text=Bannerghata Road").last();
  await bannerghata.click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: "/tmp/v3_predicted_click.png" });

  console.log("errors after interactions:", JSON.stringify(errors));
})
