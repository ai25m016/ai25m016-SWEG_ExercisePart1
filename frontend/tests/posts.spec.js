// frontend/tests/posts.spec.js
const { test, expect } = require("@playwright/test");
const path = require("path");

const FRONTEND_URL = "http://127.0.0.1:5500/index.html";
const CAT_PNG = path.resolve(__dirname, "fixtures", "cat.png");

async function createPost(page, { text, user }) {
  await page.goto(FRONTEND_URL);
  await expect(page.locator("h1")).toHaveText(/Simple Social/i);

  await page.setInputFiles("#image", CAT_PNG);
  await page.fill("#text", text);
  await page.fill("#user", user);

  await page.click('button[type="submit"]');
  await expect(page.locator("#status")).toContainText("Post erstellt", { timeout: 20000 });

  // neu laden damit UI sicher den neuen Stand rendert
  await page.click("#reload-posts");
}

test.describe("Simple Social", () => {
  test("can create a post and see it in the list", async ({ page }) => {
    const unique = Date.now();
    const user = "testuser";
    const text = `Hello from Playwright! ${unique}`;

    await createPost(page, { text, user });

    await expect(page.locator("#posts-container")).toContainText(text, { timeout: 20000 });
    await expect(page.locator("#posts-container")).toContainText(user, { timeout: 20000 });
  });

  test("filter by user shows only that user's posts", async ({ page }) => {
    const unique = Date.now();
    const user = "filteruser";
    const text = `Filter test ${unique}`;

    await createPost(page, { text, user });

    // Filter setzen und suchen
    await page.fill("#filter-user", user);
    await page.click("#filter-button");

    // Warte bis mindestens 1 Post da ist (nach Filter)
    const usersLocator = page.locator(".post-user");
    await expect(usersLocator.first()).toHaveText(user, { timeout: 20000 });

    // Jetzt: alle sichtbaren User-Texte einsammeln und prüfen
    const allUsers = await usersLocator.allTextContents();
    expect(allUsers.length).toBeGreaterThan(0);

    for (const u of allUsers) {
      expect(u.trim()).toBe(user);
    }

    // zusätzlich: unser Post-Text muss vorkommen
    await expect(page.locator("#posts-container")).toContainText(text, { timeout: 20000 });
  });
});
