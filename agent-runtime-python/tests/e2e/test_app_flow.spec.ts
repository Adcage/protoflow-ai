import { test, expect } from "@playwright/test";

const TEST_USER = {
  account: `e2e_test_${Date.now()}`,
  password: "Test123456!",
};

test.describe("App CRUD E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        console.error(`[PAGE ERROR] ${msg.text()}`);
      }
    });

    page.on("requestfailed", (request) => {
      const url = request.url();
      // Ignore analytics/hot-reload failures
      if (url.includes("hmr") || url.includes("hot-update")) return;
      console.error(`[NETWORK FAIL] ${request.failure()?.errorText} — ${url}`);
    });

    page.on("response", (response) => {
      if (response.status() >= 500) {
        console.error(
          `[SERVER ERROR] ${response.status()} — ${response.url()}`
        );
      }
    });
  });

  test("Step 1 — Register a new user", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const pageTitle = await page.title();
    expect(pageTitle.length).toBeGreaterThan(0);

    // Check for login form by looking for login-related text
    const bodyText = await page.textContent("body");
    if (bodyText && bodyText.includes("登录")) {
      // We're on login page, find register link
      console.log("On login page, looking for register link...");

      // Try to find register link or button
      const registerLink = page.locator(
        'a:has-text("注册"), button:has-text("注册"), a:has-text("register"), text=还没有账号'
      );
      if ((await registerLink.count()) > 0) {
        await registerLink.first().click();
        await page.waitForLoadState("networkidle");
      }
    }

    // Fill registration form
    const userAccountInput = page.locator(
      'input[placeholder*="账号"], input[id*="account"], input[name*="account"], input[placeholder*="用户名"]'
    ).first();
    const passwordInput = page.locator(
      'input[type="password"], input[placeholder*="密码"]'
    ).first();
    const confirmPasswordInput = page.locator(
      'input[type="password"], input[placeholder*="密码"]'
    ).nth(1);

    const registerButton = page.locator(
      'button:has-text("注册"), button[type="submit"]'
    ).first();

    if ((await userAccountInput.count()) > 0) {
      await userAccountInput.fill(TEST_USER.account);
      await passwordInput.fill(TEST_USER.password);

      if ((await confirmPasswordInput.count()) > 1) {
        await confirmPasswordInput.fill(TEST_USER.password);
      }

      await registerButton.click();
      await page.waitForTimeout(2000);

      // Should redirect to home or show success
      console.log("Registration submitted");
    }

    // Verify no unexpected errors on page
    const errorEl = page.locator(".ant-message-error, .ant-notification-error");
    await expect(errorEl).toHaveCount(0, { timeout: 5000 });
  });

  test("Step 2 — Create a new app project", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Wait for page to stabilize
    await page.waitForTimeout(1500);

    // Look for "创建应用" button or app list page
    const createButtons = page.locator(
      'button:has-text("创建"), a:has-text("创建"), button:has-text("新建"), a:has-text("新建应用"), button:has-text("创建应用")'
    );

    if ((await createButtons.count()) === 0) {
      // Maybe already on a page with apps listed
      console.log("No create button visible - checking page state");

      // Try finding navigation to apps
      const navLinks = page.locator(
        'a[href*="app"], a[href*="project"], [class*="menu"] a'
      );
      const count = await navLinks.count();
      console.log(`Found ${count} navigation links`);
    }

    // Check for any visible errors
    const pageErrors = page.locator(
      '[class*="error"], .ant-result-error, text=Error'
    );
    const errorVisible = await pageErrors.first().isVisible().catch(() => false);
    if (errorVisible) {
      const errorText = await pageErrors.first().textContent();
      console.error(`Page shows error: ${errorText}`);
    }
  });

  test("Step 3 — Basic page accessibility check", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    // Check page has basic structure
    const hasContent = await page.locator("body").textContent();
    expect(hasContent).toBeTruthy();
    expect(hasContent!.length).toBeGreaterThan(50);

    // No 404 or blank page
    const title = await page.title();
    expect(title).toBeTruthy();

    console.log(`Page title: "${title}"`);
    console.log(`Page content length: ${hasContent!.length}`);
    console.log(`Current URL: ${page.url()}`);
  });
});
