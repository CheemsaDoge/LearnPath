// Walk the new flow (index → clarify wizard → graph → dashboard → login) and save screenshots.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const base = process.argv[2] || "http://127.0.0.1:8000";
const out = new URL("../../docs/screenshots/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "zh-CN" });
const shot = (n) => page.screenshot({ path: `${out}${n}.png` });

const existing = process.env.GRAPH_ID;
if (!existing) {
await page.goto(base + "/login?returnTo=%2F", { waitUntil: "networkidle" });
await page.waitForTimeout(600);
await shot("11-login");
}
await page.goto(existing ? base + "/g/" + existing : base + "/", { waitUntil: "networkidle" });
if (!existing) {
await page.fill("textarea", "我想在期末前搞懂复变函数里的留数定理和围道积分");
await page.getByText("有一点基础").click();
await page.getByRole("button", { name: /开始规划学习路径/ }).click();
await page.waitForSelector("text=生成学习路径", { timeout: 120000 });
await page.waitForFunction(() => !document.body.innerText.includes("正在理解你的目标"), null, { timeout: 120000 });
await page.waitForTimeout(500);
// pick the first option of each question, add a free-text note
const chips = page.locator("li button.rounded-full");
const n = await chips.count();
if (n) await chips.nth(0).click();
await page.fill("textarea[placeholder*='软件工程专业']", "我是数学系大二学生，学过高等数学和线性代数，会一点 Python。");
await shot("12-clarify");
await page.getByRole("button", { name: /生成学习路径/ }).click();
await page.waitForURL(/\/g\//, { timeout: 60000 });
}
await page.waitForFunction(() => !document.body.innerText.includes("正在") || document.querySelectorAll(".react-flow__node").length > 5, null, { timeout: 720000 });
await page.waitForFunction(() => !document.body.innerText.includes("正在知乎上") && !document.body.innerText.includes("正在读取"), null, { timeout: 720000 });
await page.waitForTimeout(1200);
await shot("13-graph-real");

const rec = page.locator(".react-flow__node", { hasText: "推荐" }).first();
await rec.click();
await page.waitForSelector("text=开始学习这个知识点", { timeout: 20000 });
await page.getByRole("button", { name: /开始学习这个知识点/ }).click();
await page.waitForFunction(() => document.body.innerText.includes("掌握自检"), null, { timeout: 240000 });
await page.waitForTimeout(800);
await shot("14-lesson-math");

await page.goto(base + "/dashboard", { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await shot("15-dashboard-paths");
await page.getByRole("button", { name: /学习档案/ }).click();
await page.waitForTimeout(400);
await shot("16-dashboard-profile");
await page.getByRole("button", { name: /档案馆/ }).click();
await page.waitForTimeout(400);
await shot("17-dashboard-archive");
await browser.close();
console.log("done");
