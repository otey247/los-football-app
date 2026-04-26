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
        email: "reader@example.com",
        is_active: true,
        is_superuser: false,
      },
    })
  })
})

test("Blog list renders posts and navigates to detail", async ({ page }) => {
  const postId = "00000000-0000-0000-0000-000000000101"
  await page.route("**/api/v1/blog/", async (route) => {
    await route.fulfill({
      json: {
        data: [
          {
            id: postId,
            title: "Week 1 Power Rankings",
            slug: "week-1-power-rankings",
            excerpt: "The first power rankings are live.",
            published: true,
            created_at: "2026-04-26T00:00:00Z",
            updated_at: "2026-04-26T00:00:00Z",
            author_id: "00000000-0000-0000-0000-000000000001",
            author_name: "Commissioner",
          },
        ],
        count: 1,
      },
    })
  })
  await page.route(`**/api/v1/blog/${postId}**`, async (route) => {
    await route.fulfill({
      json: {
        id: postId,
        title: "Week 1 Power Rankings",
        slug: "week-1-power-rankings",
        excerpt: "The first power rankings are live.",
        content: "Team Los starts the year on top.",
        published: true,
        created_at: "2026-04-26T00:00:00Z",
        updated_at: "2026-04-26T00:00:00Z",
        author_id: "00000000-0000-0000-0000-000000000001",
        author_name: "Commissioner",
      },
    })
  })

  await page.goto("/blog")

  await expect(page.getByRole("heading", { name: "Blog" })).toBeVisible()
  await expect(page.getByText("Week 1 Power Rankings")).toBeVisible()
  await page.getByRole("link", { name: /Week 1 Power Rankings/ }).click()
  await expect(page).toHaveURL(/\/blog\/00000000-0000-0000-0000-000000000101/)
  await expect(
    page.getByRole("heading", { name: "Week 1 Power Rankings" }),
  ).toBeVisible()
  await expect(page.getByText("Team Los starts the year on top.")).toBeVisible()
})

test("Blog page shows empty state", async ({ page }) => {
  await page.route("**/api/v1/blog/", async (route) => {
    await route.fulfill({ json: { data: [], count: 0 } })
  })

  await page.goto("/blog")

  await expect(page.getByText("No posts yet")).toBeVisible()
})
