// Isolated UI regression only. Data comes from the real-browser contract test;
// HTTP responses are intercepted in this test browser, never in production code.
import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
const proof = JSON.parse(
  await fs.readFile("../docs/agent-contract-smoke.json", "utf8"),
);
const browser = await chromium.launch({ channel: "chrome", headless: true });
const results = [];
for (const width of [390, 768, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  let state = "running";
  const task = () => ({
    id: "ui-regression",
    query: "UI TEST ONLY · 实际网页证据卡片回归",
    status: state,
    created_at: "2026-10-18T06:00:00Z",
    started_at: "2026-10-18T06:00:00Z",
    ended_at: state === "running" ? null : "2026-10-18T06:01:00Z",
    error: state === "cancelled" ? "UI TEST ONLY · 已取消，已有结果保留" : null,
    result_count: proof.results.length,
    results: proof.results,
    stats: { visited: 2, candidates: 1, verified: 0, pending: 1 },
    events: proof.events
      .filter((e) => e.payload)
      .map((e, i) => ({
        ...e,
        id: i + 1,
        created_at: "2026-10-18T06:00:00Z",
        payload: { ...e.payload, image: undefined },
      }))
      .filter((e) => e.type !== "browser_snapshot"),
  });
  await page.route("**/api/tasks/ui-regression", (r) =>
    r.fulfill({ json: { data: task() } }),
  );
  await page.route("**/api/tasks/ui-regression/events?*", (r) =>
    r.fulfill({
      contentType: "text/event-stream",
      body: ": test heartbeat\n\n",
    }),
  );
  await page.route("**/api/tasks/ui-regression/cancel", (r) => {
    state = "cancelled";
    return r.fulfill({ json: { data: task() } });
  });
  await page.goto("http://127.0.0.1:3000/?task=ui-regression");
  await page
    .getByRole("heading", { name: proof.results[0].name, exact: true })
    .waitFor();
  await page.getByText("查看详情与核验证据", { exact: true }).click();
  if (
    (await page
      .getByText("中国大学生计算机设计大赛", { exact: true })
      .count()) < 1
  )
    throw new Error("Missing source evidence");
  const source = page.getByRole("link", { name: "查看来源", exact: true });
  if ((await source.getAttribute("href")) !== proof.results[0].source_urls[0])
    throw new Error("Source mismatch");
  await page.getByRole("button", { name: "取消任务" }).click();
  await page.getByText("UI TEST ONLY · 已取消，已有结果保留").waitFor();
  if (
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  )
    throw new Error("Card overflow");
  await page.screenshot({
    path: `../docs/screenshots/result-ui-test-${width}.png`,
    fullPage: true,
  });
  await page
    .getByRole("combobox", { name: "按报名状态筛选" })
    .selectOption("报名中");
  await page.getByRole("heading", { name: "没有符合筛选条件的赛事" }).waitFor();
  results.push({
    width,
    sourceLink: "PASS",
    evidenceDetails: "PASS",
    cancelState: "PASS (intercepted API)",
    filter: "PASS",
    overflow: false,
  });
  await page.close();
}
await browser.close();
await fs.writeFile(
  "../docs/ui-result-cards.json",
  JSON.stringify({ test_only: true, results }, null, 2),
);
console.log(JSON.stringify(results));
