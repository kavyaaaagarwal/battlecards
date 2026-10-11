import { expect, test } from "@playwright/test";

test("a seeded report renders its overview and battlecards", async ({ page }) => {
  await page.goto("/reports");
  await page.getByText("Netchex").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Netchex vs Paylocity");
  await expect(page.getByText("Who leads where")).toBeVisible();
  await expect(page.getByText(/Biggest threat:/)).toBeVisible();

  await page.getByLabel("Key buyer").selectOption("economic");
  await page.getByLabel("Stage").selectOption("proposal");
  await expect(page).not.toHaveURL(/role=economic/); // nothing changes until Apply
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page).toHaveURL(/stage=proposal&role=economic/);
  await expect(page.getByText("Digital reputation")).toBeVisible();
  await expect(page.locator(".tm-grid thead th.focus").first()).toContainText("Pricing");

  await page.locator("nav.tabs").getByRole("link", { name: "vs Paylocity" }).click();
  await expect(page).toHaveURL(/tab=paylocity.*role=economic/); // the deal follows the rep across tabs
  await expect(page.getByText("Deal brief")).toBeVisible();
  await expect(page.locator(".db-moves li")).toHaveCount(3);
  await expect(page.getByText("When they come up, say")).toBeVisible();
  await expect(page.getByText("Our edge")).toBeVisible();
  await page.getByText("More detail").click();
  await expect(page.getByText("Review ratings")).toBeVisible();
  expect(await page.locator(".ev, .sup").count()).toBeGreaterThan(5); // every point shows its evidence badge

  await expect(page.locator(".dbl-row.hot").first()).toContainText("Pricing");

  const res = await page.request.get(page.url().replace(/\?.*/, "").replace("/reports/", "/api/runs/") + "/export");
  expect(res.ok()).toBeTruthy();
  expect(await res.text()).toContain("# Competitive intelligence: Netchex");
});

test("unknown report ids show the not-found page", async ({ page }) => {
  await page.goto("/reports/0000000000");
  await expect(page.getByText("Report not found")).toBeVisible();
});
