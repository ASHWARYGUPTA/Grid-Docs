import { test, expect } from "@playwright/test";

test.use({
  geolocation: { latitude: 12.969, longitude: 77.701 },
  permissions: ["geolocation"],
});

test("citizen can submit a report and see the ICT quote", async ({ page }) => {
  await page.goto("/report");

  await page.getByRole("button", { name: "Share my location" }).click();
  await expect(page.getByText("Location captured.")).toBeVisible({ timeout: 8000 });

  const tinyJpegBytes = Buffer.from(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcICggHCAoNCwwLDQ8" +
      "ODg4PFhMTFhYPFRcXGRoYFhgbHCAlIBwgGyAjJCEhJSouLi4qNzU3PUBA" +
      "QkRGSkBKVlZWVlb/2wBDAQkJCQwMDA4ODg4SEhUVFhYWFhYWFhYWFhYW" +
      "FhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFv/AABEIAAEA" +
      "AQMBIgACEQEDEQH/xAAUAAEAAAAAAAAAAAAAAAAAAAAI/8QAFBABAAAA" +
      "AAAAAAAAAAAAAAAAAP/EABQBAQAAAAAAAAAAAAAAAAAAAAj/xAAUEQEA" +
      "AAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
    "base64"
  );

  await page.setInputFiles('input[type="file"]', {
    name: "photo.jpg",
    mimeType: "image/jpeg",
    buffer: tinyJpegBytes,
  });

  await page.getByRole("button", { name: "Submit report" }).click();

  await expect(page.getByRole("main").getByText("Report submitted")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText(/Typical clearance/)).toBeVisible();
});
