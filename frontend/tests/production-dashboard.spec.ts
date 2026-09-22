import { expect, test } from "@playwright/test";
const url = (n: number) =>
  "/productions/00000000-0000-0000-0000-" +
  String(n).padStart(12, "0") +
  "/dashboard";

test("production dashboard shows measured readiness and honest unavailable metrics", async ({
  page,
}, testInfo) => {
  await page.goto("/productions");
  await page.getByRole("link", { name: "Video6", exact: true }).click();
  await expect(page).toHaveURL(/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Video #6", exact: true }),
  ).toBeVisible();
  for (const title of [
    "Progress",
    "Assets Ready",
    "Missing Assets",
    "AI Gaps",
    "Sync Status",
    "Import Queue",
    "Latest Imports",
    "Credits Saved",
  ]) {
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
  }
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "25");
  await expect(page.getByText("Not tracked", { exact: true })).toHaveCount(2);
  await expect(page.getByText("Latest.mov", { exact: true })).toBeVisible();
  await expect(
    page.getByText(/not attributed to this production/),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("production-dashboard.png"),
    fullPage: true,
  });
});

test("empty and failed dashboard data never imply completion", async ({
  page,
}) => {
  await page.goto(url(2));
  await expect(page.getByText("Not planned", { exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  await expect(
    page.getByText("No recorded runs", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No completed imports" }),
  ).toBeVisible();
  for (const n of [3, 4]) {
    await page.goto(url(n));
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Temporarily unavailable",
    );
    await expect(page.getByRole("progressbar")).toHaveCount(0);
  }
});
