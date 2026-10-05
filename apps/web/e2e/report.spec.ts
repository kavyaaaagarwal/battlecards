import { expect, test } from "@playwright/test";

test("a seeded report renders its overview and battlecards", async ({ page }) => {
  await page.goto("/reports");
  await page.getByText("Netchex").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Netchex vs Paylocity");
  await expect(page.getByText("Capability comparison")).toBeVisible();

  await page.getByRole("link", { name: "vs Paylocity" }).click();
  await expect(page).toHaveURL(/tab=paylocity/);
  await expect(page.getByText("Capability scorecard")).toBeVisible();
  await expect(page.getByText("Evidence quality")).toBeVisible();
  expect(await page.locator("sup.cite a").count()).toBeGreaterThan(5);

  const res = await page.request.get(page.url().replace(/\?.*/, "").replace("/reports/", "/api/runs/") + "/export");
  expect(res.ok()).toBeTruthy();
  expect(await res.text()).toContain("# Competitive intelligence: Netchex");
});

test("unknown report ids show the not-found page", async ({ page }) => {
  await page.goto("/reports/0000000000");
  await expect(page.getByText("Report not found")).toBeVisible();
});
