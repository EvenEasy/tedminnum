import { test, expect } from "@playwright/test";

test("Vite preserves browser Origin; login, cookies, refresh, CSRF and logout work", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("admin@e2e.test");
  await page.getByLabel("Password", { exact: true }).fill("wrong-password");
  await page.getByRole("button", { name: "Sign in →" }).click();
  await expect(page.getByRole("alert")).toContainText("Invalid credentials");
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-test-password-123");
  const requestPromise = page.waitForRequest(
    (r) => r.url().endsWith("/api/v1/auth/login") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Sign in →" }).click();
  const request = await requestPromise;
  expect(await request.headerValue("origin")).toBe("http://127.0.0.1:5173");
  await expect(
    page.getByRole("heading", { name: "Hello, Test." }),
  ).toBeVisible();
  const cookie = (await context.cookies()).find(
    (c) => c.name === "ted_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  expect(cookie?.secure).toBe(false);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Hello, Test." }),
  ).toBeVisible();
  const me = await page.request.get("/api/v1/auth/me");
  expect(me.status()).toBe(200);
  const rejected = await page.request.post("/api/v1/auth/logout", {
    headers: {
      Origin: "http://evil.example",
      "X-CSRF-Token": (await me.json()).csrf,
    },
  });
  expect(rejected.status()).toBe(403);
  expect(await rejected.json()).toEqual({ detail: "Origin rejected" });
  const csrf = await page.request.post("/api/v1/auth/logout", {
    headers: { Origin: "http://127.0.0.1:5173", "X-CSRF-Token": "invalid" },
  });
  expect(csrf.status()).toBe(403);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
});
