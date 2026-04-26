import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("access_token", "test-token")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      json: {
        id: "00000000-0000-0000-0000-000000000001",
        email: "admin@example.com",
        is_active: true,
        is_superuser: true,
      },
    })
  })
})

test("Fantasy Stats page filters categories and expands a stat card", async ({
  page,
}) => {
  await page.route("**/api/v1/sleeper/meta", async (route) => {
    await route.fulfill({
      json: [
        {
          key: "all-play-record",
          title: "All-Play Record",
          description: "Virtual record against every team.",
          category: "Power Rankings",
        },
        {
          key: "waiver-roi",
          title: "Waiver ROI",
          description: "Points gained from adds.",
          category: "Waivers",
        },
      ],
    })
  })
  await page.route(
    "**/api/v1/sleeper/stats/all-play-record**",
    async (route) => {
      await route.fulfill({
        json: [
          {
            roster_id: 1,
            display_name: "Commissioner",
            all_play_wins: 8,
            all_play_losses: 3,
            all_play_ties: 0,
          },
        ],
      })
    },
  )

  await page.goto("/fantasy-stats")
  await expect(
    page.getByRole("heading", { name: "Fantasy Stats" }),
  ).toBeVisible()

  await page.getByLabel("Sleeper League ID").fill("12345")
  await page.getByRole("button", { name: "Load League" }).click()
  await expect(page.getByText("League ID set:")).toBeVisible()

  await page
    .locator(".rounded-xl")
    .filter({ hasText: "All-Play Record" })
    .getByRole("button")
    .click()
  const allPlayCard = page.locator(".rounded-xl").filter({
    hasText: "All-Play Record",
  })
  await expect(allPlayCard).toContainText("Commissioner")
  await expect(allPlayCard).toContainText("all play wins")

  await page.getByRole("combobox").click()
  await page.getByRole("option", { name: "Waivers" }).click()
  await expect(page.getByText("Waiver ROI")).toBeVisible()
  await expect(page.getByText("All-Play Record")).not.toBeVisible()
})

test("Fantasy Stats page shows an error if stat metadata fails", async ({
  page,
}) => {
  await page.route("**/api/v1/sleeper/meta", async (route) => {
    await route.fulfill({ status: 500, json: { detail: "failed" } })
  })

  await page.goto("/fantasy-stats")

  await expect(
    page.getByText("Unable to load fantasy stat cards"),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible()
})
