import { chromium } from "playwright";
const base = "http://127.0.0.1:8000";
const out = "/home/admin/cheemsadoge/learnway/docs/screenshots/";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "zh-CN" });
// build up a guest profile via API in the same browser context (cookie-bound)
await page.goto(base + "/", { waitUntil: "networkidle" });
await page.evaluate(async () => {
  await fetch("/api/me/facts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "background", text: "数学系大二学生" }) });
  await fetch("/api/me/facts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "skill", text: "学过高等数学和线性代数，会一点 Python" }) });
  await fetch("/api/me/facts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "goal", text: "期末前搞懂留数定理与围道积分" }) });
  await fetch("/api/me/facts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "preference", text: "喜欢先看例子再看推导" }) });
  const blob = new Blob(["复变函数期末考试范围\n1. 解析函数与柯西-黎曼方程\n2. 柯西积分定理与积分公式\n3. 留数定理及其应用"], { type: "text/plain" });
  const fd = new FormData(); fd.append("file", blob, "复变函数考试范围.txt");
  await fetch("/api/attachments", { method: "POST", body: fd });
});
await page.goto(base + "/dashboard", { waitUntil: "networkidle" });
await page.getByRole("button", { name: /学习档案/ }).click();
await page.waitForTimeout(500);
await page.screenshot({ path: out + "16-dashboard-profile.png" });
await page.getByRole("button", { name: /档案馆/ }).click();
await page.waitForTimeout(400);
await page.screenshot({ path: out + "17-dashboard-archive.png" });
await page.getByRole("button", { name: /^附件/ }).click();
await page.waitForTimeout(400);
await page.screenshot({ path: out + "18-dashboard-files.png" });
await browser.close();
console.log("ok");
