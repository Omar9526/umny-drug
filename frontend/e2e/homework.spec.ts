import { expect, test } from "@playwright/test";
import { createFamily, loginAsChild, skipUnlessDemo } from "./helpers";

test.beforeEach(async ({ request }) => {
  await skipUnlessDemo(request);
});

test("typed homework → confirmation → streamed explanation → verified answer → result", async ({
  page,
  request,
}) => {
  const { familyCode, pin, nickname } = await createFamily(request);
  await loginAsChild(page, familyCode, nickname, pin);

  await page.goto("/assignments/new?source=text");
  await page.getByRole("textbox").fill("12 * 4 = ?");
  await page.getByRole("button", { name: "Отправить" }).click();

  await expect(page).toHaveURL(/\/assignments\/.+\/confirm/, {
    timeout: 60_000,
  });
  await expect(page.getByLabel(/Текст задания/)).toHaveValue("12 * 4 = ?");
  await expect(
    page.getByRole("button", { name: /Математика/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Всё верно, разбираем" }).click();

  await expect(page).toHaveURL(/\/sessions\//, { timeout: 60_000 });
  await expect(page.getByText("Давай разберёмся")).toBeVisible({
    timeout: 60_000,
  });
  await expect(
    page.getByText("Какой ответ у тебя получился?").first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "Дай подсказку" }).click();
  await expect(page.getByText("Подсказка:")).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "Проверь ответ" }).click();
  await page.locator("input[inputmode=decimal]").fill("48");
  await page.locator("form").getByRole("button", { name: "Проверить" }).click();

  await expect(page.getByText("Верно!").first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText("проверено вычислением")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Готово!" })).toBeVisible();
  await expect(page.getByText("1 подсказка")).toBeVisible();

  await page.goto("/history");
  await expect(page.getByText("Выполнено").first()).toBeVisible();
});

test("a wrong answer stays in the session and is explained", async ({
  page,
  request,
}) => {
  const { familyCode, pin, nickname } = await createFamily(request);
  await loginAsChild(page, familyCode, nickname, pin);

  await page.goto("/ask?mode=question");
  await page.getByRole("textbox").fill("7 + 8 = ?");
  await page.getByRole("button", { name: "Начать" }).click();
  await expect(page).toHaveURL(/\/sessions\//);
  await expect(page.getByText("Давай разберёмся")).toBeVisible({
    timeout: 60_000,
  });

  await page.getByRole("button", { name: "Проверь ответ" }).click();
  await page.locator("input[inputmode=decimal]").fill("16");
  await page.locator("form").getByRole("button", { name: "Проверить" }).click();
  await expect(page.getByText("Пока нет").first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(
    page.getByRole("button", { name: "Проверь ответ" }),
  ).toBeVisible();
});

test("other family's session is not reachable", async ({ page, request }) => {
  const a = await createFamily(request);
  const b = await createFamily(request);

  await loginAsChild(page, a.familyCode, a.nickname, a.pin);
  await page.goto("/ask?mode=question");
  await page.getByRole("textbox").fill("2 + 2 = ?");
  await page.getByRole("button", { name: "Начать" }).click();
  await expect(page).toHaveURL(/\/sessions\//);
  const sessionUrl = page.url();

  await page.goto("/profile");
  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(page.getByRole("button", { name: "Я ученик" })).toBeVisible();

  await loginAsChild(page, b.familyCode, b.nickname, b.pin);
  await page.goto(sessionUrl);
  await expect(page.getByText("Не найдено")).toBeVisible();
});
