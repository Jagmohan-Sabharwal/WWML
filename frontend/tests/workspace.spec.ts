import { expect, test } from "@playwright/test";

test("root opens dashboard and navigation identifies all four pages", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Every story starts here." }),
  ).toBeVisible();
  await expect(page.getByText("14", { exact: true })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("dashboard.png"),
    fullPage: true,
  });
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  for (const title of ["Assets", "Productions", "Settings", "Dashboard"]) {
    await nav.getByRole("link", { name: title, exact: true }).click();
    await expect(
      nav.getByRole("link", { name: title, exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(page).toHaveTitle(new RegExp(title + " · WWML"));
  }
  await expect(
    page.getByRole("heading", { name: "Recently added" }),
  ).toBeVisible();
});

test("search and pagination preserve the media filter", async ({
  page,
}, testInfo) => {
  await page.goto("/assets");
  await page.getByLabel("Search library").fill("Coast");
  await page.getByLabel("Media type").selectOption("video");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("13 assets matching your search")).toBeVisible();
  await page.getByRole("link", { name: "Next", exact: true }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByLabel("Search library")).toHaveValue("Coast");
  await expect(page.getByLabel("Media type")).toHaveValue("video");
  await expect(
    page.getByText("Coast interview 13", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Page 2 of 2")).toBeVisible();
  await page.getByRole("link", { name: "Clear filters" }).click();
  await expect(page.getByText("14 assets in your library")).toBeVisible();
});

test("empty, unavailable and malformed responses remain usable", async ({
  page,
}) => {
  await page.goto("/assets?q=no-matching-footage");
  await expect(
    page.getByRole("heading", { name: "No matching assets" }),
  ).toBeVisible();
  for (const query of ["unavailable", "malformed"]) {
    await page.goto("/assets?q=" + query);
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Temporarily unavailable",
    );
    await expect(page.getByText("private-upstream-error")).toHaveCount(0);
    await expect(
      page.getByRole("navigation", { name: "Main navigation" }),
    ).toBeVisible();
  }
});

test("invalid URL parameters are normalized and search works after navigation", async ({
  page,
}) => {
  await page.goto("/assets?page=-4&media_type=not-real&q=Coast");
  await expect(page.getByText("13 assets matching your search")).toBeVisible();
  await expect(page.getByLabel("Media type")).toHaveValue("");
  await page.getByLabel("Search library").fill("Forest");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Forest soundscape")).toBeVisible();
});

test("appearance persists and platform reports real readiness", async ({
  page,
}) => {
  await page.goto("/settings");
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: "dark", exact: true }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(
    page.getByRole("radio", { name: "dark", exact: true }),
  ).toBeChecked();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("radio", { name: "light", exact: true }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("productions lists real records and pages fit viewport", async ({
  page,
}) => {
  for (const path of ["/dashboard", "/assets", "/productions", "/settings"]) {
    await page.goto(path);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.goto("/productions");
  await expect(page.getByRole("heading", { name: "Video6" })).toBeVisible();
  await page.getByRole("link", { name: "Open editor" }).click();
  await expect(page).toHaveURL(/\/editor$/);
});

test("not found pages provide a way back", async ({ page }) => {
  const response = await page.goto("/missing-page");
  expect(response?.status()).toBe(404);
  await page.getByRole("link", { name: "Return to dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("health proxy is preserved", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({
    status: "ok",
    checks: { postgres: true, redis: true },
  });
});
