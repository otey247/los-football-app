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

test("Super Admin page lists blog posts and opens create dialog", async ({
  page,
}) => {
  await page.route("**/api/v1/blog/admin", async (route) => {
    await route.fulfill({
      json: {
        data: [
          {
            id: "00000000-0000-0000-0000-000000000201",
            title: "Commissioner Notes",
            slug: "commissioner-notes",
            excerpt: "Trade deadline reminders.",
            content: "Remember to set your lineups.",
            published: false,
            created_at: "2026-04-26T00:00:00Z",
            updated_at: "2026-04-26T00:00:00Z",
            author_id: "00000000-0000-0000-0000-000000000001",
            author_name: "Admin",
          },
        ],
        count: 1,
      },
    })
  })

  await page.goto("/super-admin")

  await expect(page.getByRole("heading", { name: "Super Admin" })).toBeVisible()
  await expect(page.getByText("Commissioner Notes")).toBeVisible()
  await expect(page.getByText("Draft")).toBeVisible()

  await page.getByRole("button", { name: "New Post" }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "New Blog Post" }),
  ).toBeVisible()
})

test("Super Admin page shows an error state if posts fail to load", async ({
  page,
}) => {
  await page.route("**/api/v1/blog/admin", async (route) => {
    await route.fulfill({ status: 500, json: { detail: "failed" } })
  })

  await page.goto("/super-admin")

  await expect(page.getByText("Unable to load blog posts")).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible()
})
