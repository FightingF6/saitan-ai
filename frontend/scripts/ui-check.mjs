import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
const browser = await chromium.launch({ channel: "chrome", headless: true });
const errors = [];
const results = [];
await fs.mkdir("../docs/screenshots", { recursive: true });
for (const width of [390, 768, 1440]) {
  const page = await browser.newPage({
    viewport: { width, height: 1000 },
    deviceScaleFactor: 1,
  });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:3000");
  await page.getByText("Agent 服务在线").waitFor({ state: "attached" });
  await page.getByRole("button", { name: "适合大一新手参加的比赛" }).click();
  const query = await page
    .getByRole("textbox", { name: "竞赛搜索需求" })
    .inputValue();
  if (query !== "适合大一新手参加的比赛")
    throw new Error("Example fill failed");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  if (overflow) throw new Error(`Horizontal overflow at ${width}`);
  await page.screenshot({
    path: `../docs/screenshots/home-${width}.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "开始搜索" }).click();
  await page.getByRole("alert").filter({ hasText: "模型尚未配置" }).waitFor();
  for (const [url, label] of [
    ["/tasks", "每一次探索，都有记录"],
    ["/competitions", "让好机会，成为你的收藏"],
    ["/settings", "配置好，一起去探索"],
  ]) {
    await page.goto(`http://127.0.0.1:3000${url}`);
    await page.getByRole("heading", { name: label }).waitFor();
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw new Error(`Overflow ${url} ${width}`);
  }
  await page.screenshot({
    path: `../docs/screenshots/settings-${width}.png`,
    fullPage: true,
  });
  results.push({
    width,
    pages: 4,
    overflow: false,
    exampleFill: "PASS",
    unconfiguredError: "PASS",
  });
  await page.close();
}
await browser.close();
if (errors.length) throw new Error(errors.join("\n"));
await fs.writeFile(
  "../docs/ui-results.json",
  JSON.stringify({ results, consoleErrors: errors }, null, 2),
);
console.log(JSON.stringify(results));
