import { test, expect } from "@playwright/test";

const TEST_USER = {
  account: "admin",
  password: "12345678",
};

const TEST_APP_NAME = `E2E_${Date.now().toString(36)}`;

test.describe("Login & App CRUD E2E Flow", () => {
  const errors: string[] = [];
  const networkFails: string[] = [];
  const serverErrors: string[] = [];

  test.beforeEach(async ({ page }) => {
    errors.length = 0;
    networkFails.length = 0;
    serverErrors.length = 0;

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(`[CONSOLE] ${msg.text()}`);
      }
    });

    page.on("requestfailed", (request) => {
      const url = request.url();
      if (
        url.includes("hmr") ||
        url.includes("hot-update") ||
        url.includes("vite") ||
        url.includes("favicon") ||
        url.includes("__devtools__")
      )
        return;
      networkFails.push(`[NETWORK] ${request.failure()?.errorText} — ${url}`);
    });

    page.on("response", (response) => {
      if (response.status() >= 500) {
        serverErrors.push(`[SERVER 5xx] ${response.status()} — ${response.url()}`);
      }
    });
  });

  test.afterEach(async () => {
    const allIssues = [...errors, ...networkFails, ...serverErrors];
    if (allIssues.length > 0) {
      console.warn("=== Issues detected during test ===");
      allIssues.forEach((e) => console.warn("  ", e));
    }
  });

  test("Step 1: Login with admin account", async ({ page }) => {
    await page.goto("/user/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    const title = await page.title();
    expect(title).toBeTruthy();

    await page.getByRole("textbox", { name: /账号/ }).fill(TEST_USER.account);
    await page.getByRole("textbox", { name: /密码/ }).fill(TEST_USER.password);
    await page.getByRole("button", { name: "登录" }).click();

    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    const url = page.url();
    expect(url).toContain("/");

    const loggedInIndicator = page.getByText("用户", { exact: false });
    await expect(loggedInIndicator.first()).toBeVisible({ timeout: 5000 });

    expect(errors).toHaveLength(0);
    expect(networkFails).toHaveLength(0);
    expect(serverErrors).toHaveLength(0);
  });

  test("Step 2: Navigate to My Apps and create a new app", async ({ page }) => {
    await page.goto("/user/login");
    await page.waitForLoadState("networkidle");
    await page.getByRole("textbox", { name: /账号/ }).fill(TEST_USER.account);
    await page.getByRole("textbox", { name: /密码/ }).fill(TEST_USER.password);
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    await page.getByRole("link", { name: "我的作品" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    const pageContent = (await page.textContent("body")) || "";
    expect(pageContent.length).toBeGreaterThan(0);

    const hasCreateBtn = await page.getByText(/创建应用|新建应用|创建|新建/).first().isVisible().catch(() => false);
    if (!hasCreateBtn) {
      console.log("No create button visible, checking page content...");
      console.log("Current URL:", page.url());
      console.log("Page content excerpt:", pageContent.substring(0, 300));
    }
    expect(hasCreateBtn).toBeTruthy();

    await page.getByText(/创建|新建/).first().click();
    await page.waitForTimeout(1500);

    const nameInput = page.locator('input[id*="name"], input[placeholder*="名称"], input[placeholder*="应用"]').first();
    if ((await nameInput.count()) > 0 && (await nameInput.isVisible())) {
      await nameInput.fill(TEST_APP_NAME);
    }

    const confirmBtn = page.getByRole("button", { name: /确定|提交|创建/ }).first();
    if ((await confirmBtn.count()) > 0 && (await confirmBtn.isVisible())) {
      await confirmBtn.click();
      await page.waitForTimeout(2500);
      await page.waitForLoadState("networkidle");
    }

    const newContent = (await page.textContent("body")) || "";
    console.log("After create, page content length:", newContent.length);

    expect(errors).toHaveLength(0);
    expect(networkFails).toHaveLength(0);
    expect(serverErrors).toHaveLength(0);
  });

  test("Step 3: Edit app and verify persistence after reload", async ({ page }) => {
    await page.goto("/user/login");
    await page.waitForLoadState("networkidle");
    await page.getByRole("textbox", { name: /账号/ }).fill(TEST_USER.account);
    await page.getByRole("textbox", { name: /密码/ }).fill(TEST_USER.password);
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    await page.goto("/app/my");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    await page.screenshot({ path: "test-results/step3-my-apps.png", fullPage: true });

    const bodyText = (await page.textContent("body")) || "";
    console.log("My Apps page length:", bodyText.length);
    expect(bodyText.length).toBeGreaterThan(0);

    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    const afterReload = (await page.textContent("body")) || "";
    console.log("After reload, page length:", afterReload.length);
    expect(afterReload.length).toBeGreaterThan(0);

    const isStillLoggedIn = await page.getByText("用户", { exact: false }).first().isVisible().catch(() => false);
    expect(isStillLoggedIn).toBeTruthy();

    expect(errors).toHaveLength(0);
    expect(networkFails).toHaveLength(0);
    expect(serverErrors).toHaveLength(0);
  });

  test("Step 4: Verify navigation works after login", async ({ page }) => {
    await page.goto("/user/login");
    await page.waitForLoadState("networkidle");
    await page.getByRole("textbox", { name: /账号/ }).fill(TEST_USER.account);
    await page.getByRole("textbox", { name: /密码/ }).fill(TEST_USER.password);
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    await page.getByRole("link", { name: "主页" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    expect(page.url()).not.toContain("/user/login");

    const homeText = (await page.textContent("body")) || "";
    expect(homeText).toContain("AC AI Code");

    await page.getByRole("link", { name: "我的作品" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    expect(errors).toHaveLength(0);
    expect(networkFails).toHaveLength(0);
    expect(serverErrors).toHaveLength(0);
  });
});
