// frontend/tests/posts.spec.js
const { test, expect } = require('@playwright/test');

const FRONTEND_URL = 'http://127.0.0.1:5500/index.html';

test('can create a post and see it in the list', async ({ page }) => {
  // Open your frontend
  await page.goto(FRONTEND_URL);

  // Fill the form
  await page.fill('#image', 'cat.png');
  await page.fill('#text', 'Hello from Playwright!');
  await page.fill('#user', 'testuser');

  // Submit
  await page.click('button[type="submit"]');

  // Wait a bit for the backend to respond and UI to update
  await page.waitForTimeout(500);

  // Check that the new post appears
  const firstPostText = await page.locator('.post p').last().textContent();
  expect(firstPostText).toContain('Hello from Playwright!');

  const firstPostUser = await page.locator('.post-user').last().textContent();
  expect(firstPostUser).toContain('testuser');
});

test('filter by user shows only that user\'s posts', async ({ page }) => {
  await page.goto(FRONTEND_URL);

  // Assumes there is at least one post from "testuser" (from previous test)
  await page.fill('#filter-user', 'testuser');
  await page.click('#filter-button');

  await page.waitForTimeout(500);

  const allUsers = await page.locator('.post-user').allTextContents();
  for (const user of allUsers) {
    expect(user).toContain('testuser');
  }
});

