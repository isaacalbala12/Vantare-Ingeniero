import { test, expect } from "@playwright/test";

const EXPECTED_BACKEND_ERROR_PATTERNS = [
  /Failed to load resource:\s*net::ERR_CONNECTION_REFUSED/,
  /\[api\] Error fetching health:\s*TypeError:\s*Failed to fetch/,
  /WebSocket connection to 'ws:\/\/localhost:8008\/ws' failed/,
  /\[useWebSocket\] Error de conexión:\s*Event/,
];

function isExpectedBackendError(text: string): boolean {
  return EXPECTED_BACKEND_ERROR_PATTERNS.some((re) => re.test(text));
}

test("smoke: Vite dev server loads homepage without errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });
  page.on("pageerror", (err) => {
    consoleErrors.push(err.message);
  });

  await page.goto("/");

  // Assert page title contains "Vantare" (visible in App.tsx title bar)
  await expect(page).toHaveTitle(/Vantare/i);

  // Assert no unexpected console errors on load
  const unexpectedErrors = consoleErrors.filter((text) => !isExpectedBackendError(text));
  expect(unexpectedErrors).toEqual([]);
});
