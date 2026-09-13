// Drive the app in a headless browser and capture screenshots for README / submission docs.
// Usage (from frontend/): npm run screenshot [-- baseUrl]   (default http://127.0.0.1:8000)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const base = process.argv[2] || "http://127.0.0.1:8000";
const out = new URL("../../docs/screenshots/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "zh-CN" });
const shot = (name) => page.screenshot({ path: `${out}${name}.png` });

await page.goto(base + "/", { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await shot("01-home");

await page.fill("textarea", "我想搞懂 Transformer，能读懂论文和源码");
await page.getByText("有一点基础").click();
await page.getByRole("button", { name: /生成我的学习路径/ }).click();
await page.waitForURL(/\/g\//, { timeout: 30000 });
await page.waitForTimeout(1500);
await shot("02-generating");

// wait until the graph is ready (status banner disappears) — up to 4 minutes
await page.waitForFunction(() => !document.body.innerText.includes("正在") || document.querySelectorAll(".react-flow__node").length > 5, null, { timeout: 720000 });
await page.waitForFunction(() => !document.body.innerText.includes("正在知乎上") && !document.body.innerText.includes("正在读取"), null, { timeout: 720000 });
await page.waitForTimeout(1500);
await shot("03-graph");

// open the recommended node
const rec = page.locator(".react-flow__node", { hasText: "推荐" }).first();
await rec.click();
await page.waitForSelector("text=开始学习这个知识点", { timeout: 20000 });
await page.waitForTimeout(500);
await shot("04-node-panel");

await page.getByRole("button", { name: /开始学习这个知识点/ }).click();
await page.waitForSelector("text=重新生成", { timeout: 60000 });
await page.waitForFunction(() => document.body.innerText.includes("掌握自检"), null, { timeout: 120000 });
await page.waitForTimeout(800);
await shot("05-lesson");

await page.getByRole("button", { name: /知乎来源/ }).click();
await page.waitForTimeout(600);
await shot("06-sources");

await page.getByRole("button", { name: /小测验/ }).click();
await page.getByRole("button", { name: /生成小测验/ }).click();
await page.waitForSelector("text=提交并评分", { timeout: 90000 });
const options = page.locator("button", { hasText: /^[A-D]\./ });
const count = await options.count();
for (let i = 0; i < count; i += 4) await options.nth(Math.min(i + 1, count - 1)).click();
await page.locator("textarea").last().fill("它把输入序列映射为输出序列，核心是注意力机制：让每个位置都能关注到其他位置的信息，例如翻译时对齐相关的词。");
await page.waitForTimeout(400);
await shot("07-quiz");
await page.getByRole("button", { name: /提交并评分/ }).click();
await page.waitForSelector("text=再来一组", { timeout: 120000 });
await page.waitForTimeout(800);
await shot("08-quiz-result");

await page.getByRole("button", { name: /复习卡片/ }).click();
await page.getByRole("button", { name: /生成复习卡片/ }).click();
await page.waitForSelector("text=点击翻面", { timeout: 90000 });
await page.locator("button", { hasText: "卡片 1" }).click();
await page.waitForTimeout(500);
await shot("09-cards");

await page.getByRole("button", { name: /讲解对话/ }).click();
await page.fill("input[placeholder*='接着问导师']", "为什么需要注意力机制？");
await page.keyboard.press("Enter");
await page.waitForTimeout(4000);
await shot("10-chat");

await browser.close();
console.log("screenshots saved to", out);
