import { test, expect } from "@playwright/test";

test("admin-managed work → persistent member timer → issued PDF invoice → payment", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("admin@e2e.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-test-password-123");
  await page.getByRole("button", { name: "Sign in →" }).click();
  await expect(
    page.getByRole("heading", { name: "Hello, Test." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Add person" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Full name").fill("Taylor Member");
  await dialog.getByLabel("Email").fill("member@e2e.test");
  await dialog
    .getByLabel("Temporary password")
    .fill("member-test-password-123");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Clients", exact: true }).click();
  await page.getByRole("button", { name: "New client" }).click();
  await dialog.getByLabel("Client name").fill("Real client");
  await dialog.getByLabel("Default hourly rate").fill("120.00");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await page.getByRole("button", { name: "New project" }).click();
  await dialog.getByLabel("Project name").fill("Local launch");
  await dialog
    .getByLabel("Client", { exact: true })
    .selectOption({ label: "Real client" });
  await dialog.getByLabel("Taylor Member").check();
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Tasks", exact: true }).click();
  await page.getByRole("button", { name: "New task" }).click();
  await dialog.getByLabel("Title", { exact: true }).fill("Ship the app");
  await dialog
    .getByLabel("Project", { exact: true })
    .selectOption({ label: "Local launch" });
  await dialog.getByLabel("Taylor Member").check();
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();

  const memberContext = await browser.newContext();
  const member = await memberContext.newPage();
  await member.goto("/");
  await member.getByLabel("Email", { exact: true }).fill("member@e2e.test");
  await member
    .getByLabel("Password", { exact: true })
    .fill("member-test-password-123");
  await member.getByRole("button", { name: "Sign in →" }).click();
  await expect(
    member.getByRole("heading", { name: "Hello, Taylor." }),
  ).toBeVisible();
  await expect(
    member.getByRole("button", { name: "Invoices", exact: true }),
  ).toHaveCount(0);
  await member.getByLabel("Timer task").selectOption({ label: "Ship the app" });
  await member.getByRole("button", { name: "Start session" }).click();
  await expect(
    member.getByRole("button", { name: "Stop & save" }),
  ).toBeVisible();
  await member.reload();
  await expect(
    member.getByRole("button", { name: "Stop & save" }),
  ).toBeVisible();
  await member.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(
    member.getByRole("button", { name: "Resume", exact: true }),
  ).toBeVisible();
  await member.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(member.locator(".timer-value")).toHaveText(
    /^\d{2}:\d{2}:\d{2}$/,
  );
  await expect(
    member.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
  await member.getByRole("button", { name: "Stop & save" }).click();
  await member.getByRole("button", { name: "Time", exact: true }).click();
  await member.getByRole("button", { name: "Adjust" }).click();
  const md = member.getByRole("dialog");
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  yesterday.setHours(12, 0, 0, 0);
  const local = (d: Date) =>
    new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 19);
  await md
    .getByLabel("Started", { exact: true })
    .fill(local(new Date(yesterday.getTime() - 3600000)));
  await md.getByLabel("Ended", { exact: true }).fill(local(yesterday));
  await md.getByLabel("Note", { exact: true }).fill("Browser-verified hour");
  await md.getByRole("button", { name: "Save", exact: true }).click();
  await expect(md).not.toBeVisible();
  await expect(member.getByText("01:00:00", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Refresh workspace" }).click();
  await page.getByRole("button", { name: "Invoices", exact: true }).click();
  await page.getByRole("button", { name: "New invoice" }).click();
  await dialog
    .getByLabel("Client", { exact: true })
    .selectOption({ label: "Real client" });
  await dialog.getByRole("checkbox", { name: /Ship the app/ }).check();
  await dialog.getByRole("button", { name: "Create draft" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Open invoice" }).click();
  await expect(
    dialog.getByText("$120.00", { exact: true }).last(),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await dialog.getByRole("link", { name: "Download PDF" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("INV-000001.pdf");
  page.once("dialog", (d) => d.accept());
  await dialog.getByRole("button", { name: "Issue invoice" }).click();
  await expect(
    dialog.getByRole("heading", { name: "Record a payment" }),
  ).toBeVisible();
  await dialog.getByLabel("Reference (optional)").fill("E2E bank transfer");
  await dialog
    .getByRole("button", { name: "Record payment", exact: true })
    .click();
  await expect(dialog.getByText("Paid", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(
    page.locator(".stat").filter({ hasText: "Outstanding" }).getByText("$0.00"),
  ).toBeVisible();
  await expect(
    page
      .locator(".stat")
      .filter({ hasText: "Payments received" })
      .getByText("$120.00"),
  ).toBeVisible();
  // A fixed-price task logs real time but contributes exactly one fixed line.
  await page.getByRole("button", { name: "Tasks", exact: true }).click();
  await page.getByRole("button", { name: "New task" }).click();
  await dialog.getByLabel("Title", { exact: true }).fill("Fixed deliverable");
  await dialog
    .getByLabel("Project", { exact: true })
    .selectOption({ label: "Local launch" });
  await dialog.getByLabel("Billing mode").selectOption("fixed");
  await dialog.getByLabel("Fixed price (USD)").fill("250.00");
  await dialog.getByLabel("Taylor Member").check();
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await member.getByRole("button", { name: "Refresh workspace" }).click();
  await member
    .getByLabel("Timer task")
    .selectOption({ label: "Fixed deliverable" });
  await member.getByRole("button", { name: "Start session" }).click();
  await expect(
    member.getByRole("button", { name: "Stop & save" }),
  ).toBeEnabled();
  await member.getByRole("button", { name: "Stop & save" }).click();
  await member.getByRole("button", { name: "Tasks", exact: true }).click();
  await member.getByLabel("Status for Fixed deliverable").selectOption("done");
  await expect(member.getByLabel("Status for Fixed deliverable")).toHaveValue(
    "done",
  );
  await page.getByRole("button", { name: "Refresh workspace" }).click();
  await page.getByRole("button", { name: "Invoices", exact: true }).click();
  await page.getByRole("button", { name: "New invoice" }).click();
  await dialog
    .getByLabel("Client", { exact: true })
    .selectOption({ label: "Real client" });
  await dialog.getByRole("checkbox", { name: /Fixed deliverable/ }).check();
  await dialog.getByRole("button", { name: "Create draft" }).click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("row")
    .filter({ hasText: "INV-000002" })
    .getByRole("button", { name: "Open invoice" })
    .click();
  await expect(dialog.locator(".invoice-lines > div")).toHaveCount(1);
  await expect(dialog.locator(".invoice-total").first()).toContainText(
    "$250.00",
  );
  page.once("dialog", (d) => d.accept());
  await dialog.getByRole("button", { name: "Issue invoice" }).click();
  await expect(
    dialog.getByRole("heading", { name: "Record a payment" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(
    page
      .locator(".stat")
      .filter({ hasText: "Outstanding" })
      .getByText("$250.00"),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/desktop-reports.png",
    fullPage: true,
  });

  // Shared-browser sign out/sign in must not retain admin totals or projects.
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByLabel("Email", { exact: true }).fill("member@e2e.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("member-test-password-123");
  await page.getByRole("button", { name: "Sign in →" }).click();
  await expect(
    page.getByRole("heading", { name: "Hello, Taylor." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reports", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".finance")).toHaveCount(0);
  await expect(
    page.getByText("Invoice outstanding", { exact: true }),
  ).toHaveCount(0);
  await memberContext.close();
  await page.screenshot({
    path: "test-results/desktop-reports.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("mobile login, theme and active-app reminder", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("admin@e2e.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-test-password-123");
  await page.getByRole("button", { name: "Sign in →" }).click();
  await expect(
    page.getByRole("heading", { name: "Hello, Test." }),
  ).toBeVisible();
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("button", { name: "Switch to light appearance" })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByLabel("Focus minutes").fill("1");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(
    page.getByText("Focus preferences saved", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Start session" }).click();
  await expect(page.getByRole("button", { name: "Stop & save" })).toBeVisible();
  await page.screenshot({
    path: "test-results/mobile-settings.png",
    fullPage: true,
  });
  await page.clock.install();
  await page.clock.fastForward(61000);
  await expect(
    page.getByText(
      "Focus session complete. Stop work and take a break when ready.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Stop & save" }).click();
});
