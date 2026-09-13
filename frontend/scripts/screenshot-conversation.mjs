import { chromium } from "playwright";
const base = process.argv[2] || "http://127.0.0.1:8000";
const graphId = process.env.GRAPH_ID;
const out = new URL("../../docs/screenshots/", import.meta.url).pathname;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "zh-CN" });
await page.goto(`${base}/g/${graphId}`, { waitUntil: "networkidle" });
await page.waitForSelector(".react-flow__node", { timeout: 60000 });
// open the first node that already has a lesson (recommended node was taught earlier); otherwise teach it now
await page.locator(".react-flow__node", { hasText: "推荐" }).first().click();
await page.waitForSelector("text=讲解对话", { timeout: 20000 });
const needsLesson = await page.getByRole("button", { name: /开始学习这个知识点/ }).count();
if (needsLesson) {
  await page.getByRole("button", { name: /开始学习这个知识点/ }).click();
  await page.waitForFunction(() => document.body.innerText.includes("掌握自检"), null, { timeout: 240000 });
}
await page.waitForTimeout(800);
await page.screenshot({ path: `${out}19-conversation.png` });
// select a sentence inside the second tutor turn and trigger the popover
await page.evaluate(() => {
  const paras = Array.from(document.querySelectorAll(".prose-learn p")).filter((p) => (p.textContent || "").length > 30);
  const p = paras[1] || paras[0];
  const range = document.createRange();
  range.selectNodeContents(p);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  p.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
});
await page.waitForSelector("text=解释这句", { timeout: 5000 });
await page.waitForTimeout(300);
await page.screenshot({ path: `${out}20-selection-popover.png` });
await page.getByRole("button", { name: "解释这句" }).click();
await page.waitForSelector("text=临时子会话", { timeout: 5000 });
await page.waitForFunction(() => {
  const el = Array.from(document.querySelectorAll("div")).find((d) => d.textContent?.includes("临时子会话"));
  return el && !el.textContent.includes("思考中");
}, null, { timeout: 180000 });
await page.waitForTimeout(600);
await page.screenshot({ path: `${out}21-subchat-overlay.png` });
await browser.close();
console.log("ok");
