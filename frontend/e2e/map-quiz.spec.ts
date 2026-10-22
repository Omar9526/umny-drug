import { expect, test, type Page } from "@playwright/test";
import { createFamily, loginAsChild, skipUnlessDemo } from "./helpers";

test.beforeEach(async ({ request }) => {
  await skipUnlessDemo(request);
});

/** Solves one rules-generated maths question from the visible prompt (same arithmetic as the backend). */
async function solveCurrentQuestion(page: Page) {
  const prompt =
    (await page.locator("h2[data-question-prompt]").first().textContent())?.trim() ??
    "";
  const optionTexts = (
    await page.locator("[data-option-text]").allTextContents()
  ).map((t) => t.trim());
  const norm = (t: string) =>
    t
      .replace(/−/g, "-")
      .replace(/×/g, "*")
      .replace(/:/g, "/")
      .replace(/[()]/g, "");
  const frac = (t: string) => {
    const [a, b] = t.split("/").map(Number);
    return b ? a / b : a;
  };
  let m: RegExpMatchArray | null;
  if ((m = prompt.match(/Вычисли:\s*(.+)$/))) {
    const value = Function(`return (${norm(m[1])})`)() as number;
    if (optionTexts.length)
      return { choice: optionTexts.findIndex((o) => Number(o) === value) };
    return { value: String(value) };
  }
  if ((m = prompt.match(/Найди\s+(\d+)%\s+от\s+(\d+)/)))
    return { value: String((Number(m[1]) * Number(m[2])) / 100) };
  if ((m = prompt.match(/x\s*([+\-−])\s*(\d+)\s*=\s*(-?\d+)/))) {
    const a = Number(m[2]);
    const r = Number(m[3]);
    return { value: String(m[1] === "+" ? r - a : r + a) };
  }
  if (prompt.includes("дробь")) {
    const values = optionTexts.map(frac);
    return { choice: values.indexOf(Math.max(...values)) };
  }
  throw new Error(`unknown question: ${prompt}`);
}

test("knowledge map → topic → self-check quiz → topic status changes", async ({
  page,
  request,
}) => {
  const family = await createFamily(request);
  await loginAsChild(page, family.familyCode, family.nickname, family.pin);

  await page.goto("/subjects/math");
  await expect(page.getByText("Следующий шаг").first()).toBeVisible();
  await expect(page.getByText(/Пройдено 0 из \d+ тем/)).toBeVisible();
  // the map is a board of numbered tiles: tap a tile → peek panel → «Открыть тему»
  const firstTile = page.locator("button[data-topic-id]").first();
  const topicName =
    (await firstTile.getAttribute("aria-label"))?.split(":")[0] ?? "";
  await firstTile.click();
  await expect(page.getByRole("dialog", { name: topicName })).toBeVisible();
  await page.getByRole("button", { name: "Открыть тему" }).click();
  await expect(page).toHaveURL(/\/topics\/\d+$/);
  await expect(
    page.getByRole("heading", { name: topicName }).first(),
  ).toBeVisible();
  await expect(page.getByText("Ещё не изучено")).toBeVisible();

  await page.getByRole("button", { name: "Проверь себя" }).click();
  await expect(page).toHaveURL(/\/quizzes\//);
  await expect(page.getByText(/вопрос 1 из 4/i)).toBeVisible();

  for (let i = 0; i < 4; i++) {
    const plan = await solveCurrentQuestion(page);
    if (typeof plan.choice === "number") {
      await page
        .locator("button[aria-pressed]")
        .filter({ has: page.locator("[data-option-text]") })
        .nth(Math.max(plan.choice, 0))
        .click();
      await page.getByRole("button", { name: "Ответить" }).click();
    } else {
      await page.getByLabel("Твой ответ").fill(plan.value);
      await page.getByRole("button", { name: "Ответить" }).click();
    }
    await expect(page.getByText("Верно!")).toBeVisible();
    await page
      .getByRole("button", { name: i < 3 ? "Дальше" : "Завершить" })
      .click();
  }
  await expect(page.getByText("Проверка завершена")).toBeVisible();
  await expect(page.getByText("4 / 4")).toBeVisible();
  await expect(page.getByText("Статус темы: Выполнено")).toBeVisible();

  const toMap = page.getByRole("button", { name: "К карте знаний" });
  // the fixed bottom tab bar can cover an element scrolled to the viewport edge
  await toMap.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await toMap.click();
  await expect(page.getByText(/Пройдено 1 из \d+ тем/)).toBeVisible();
  await expect(
    page.locator("button[data-topic-id]").first(),
  ).toHaveAttribute("aria-label", `${topicName}: Выполнено`);
});

test("quizzes outside maths explain that the AI provider is needed in demo mode", async ({
  page,
  request,
}) => {
  const family = await createFamily(request);
  await loginAsChild(page, family.familyCode, family.nickname, family.pin);
  await page.goto("/subjects/russian");
  await expect(page.getByText("Следующий шаг").first()).toBeVisible();
  await page.locator("button[data-topic-id]").first().click();
  await page.getByRole("button", { name: "Открыть тему" }).click();
  await expect(page).toHaveURL(/\/topics\/\d+$/);
  await page.getByRole("button", { name: "Проверь себя" }).click();
  await expect(
    page.getByText("появится после подключения AI-провайдера"),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/topics\/\d+$/);
});
