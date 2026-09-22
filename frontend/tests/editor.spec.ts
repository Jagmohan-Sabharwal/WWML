import { expect, test } from "@playwright/test";

const editorPath = (n: number) =>
  "/productions/00000000-0000-0000-0000-" +
  String(n).padStart(12, "0") +
  "/editor";

test("editor shows the scene, shot, asset reference and actual readiness", async ({
  page,
}, testInfo) => {
  await page.goto("/productions");
  await page.getByRole("link", { name: "Open editor" }).click();
  const shot = page.getByRole("article", {
    name: "Luxury Bedroom",
    exact: true,
  });
  await expect(
    shot.getByText("Morning Routine", { exact: true }),
  ).toBeVisible();
  await expect(
    shot.getByText("WWML-VID-000045", { exact: true }),
  ).toBeVisible();
  await expect(shot.getByText("READY", { exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Shot 2", exact: true })
      .getByText("MISSING", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Shot 3", exact: true })
      .getByText("REVIEW", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: "Shot 4", exact: true })
      .getByText("UNPLANNED", { exact: true }),
  ).toBeVisible();
  await shot.screenshot({ path: testInfo.outputPath("editor-card.png") });
  await expect(page.locator("a[href^='file:']")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Next", exact: true }).click();
  await expect(
    page.getByRole("article", { name: "Shot 21", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(1);
});

test("editor handles empty, failed and malformed responses without false READY", async ({
  page,
}) => {
  await page.goto(editorPath(2));
  await expect(
    page.getByRole("heading", { name: "No shots planned yet" }),
  ).toBeVisible();
  for (const n of [3, 4, 9]) {
    await page.goto(editorPath(n));
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Temporarily unavailable",
    );
    await expect(page.getByText("READY", { exact: true })).toHaveCount(0);
    await expect(page.getByText("private-editor-error")).toHaveCount(0);
  }
  await page.goto(editorPath(1) + "?page=999");
  await expect(
    page.getByRole("heading", { name: "No entries on this page" }),
  ).toBeVisible();
});
