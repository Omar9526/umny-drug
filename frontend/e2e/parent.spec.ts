import { expect, test } from "@playwright/test";
import { ChildApi, createFamily, loginAsChild, loginAsParent, skipUnlessDemo } from "./helpers";

test.beforeEach(async ({ request }) => {
  await skipUnlessDemo(request);
});

test.describe.configure({ mode: "serial" });

test("parent sees real progress, reads the transcript and can hide it", async ({
  page,
  request,
}) => {
  const family = await createFamily(request);
  const child = await ChildApi.login(request, family);
  const solved = await child.typedTask("12 * 4 = ?");
  await child.checkAnswer(solved, "48");
  const review = await child.typedTask("7 * 8 = ?");
  await child.turn(review, "hint");
  await child.checkAnswer(review, "54");
  await child.complete(review);

  await loginAsParent(page, family.email, family.password);
  await expect(page.getByText("На этой неделе")).toBeVisible();
  await expect(page.getByText("2 задания")).toBeVisible();
  await expect(page.getByText(/новое уведомление/)).toBeVisible();

  await page.getByRole("link", { name: /Тест/ }).click();
  await expect(page).toHaveURL(
    new RegExp(`/parent/children/${family.childId}$`),
  );
  await expect(page.getByText("Недельный отчёт")).toBeVisible();
  await expect(page.getByText(/1 решено самостоятельно/)).toBeVisible();
  await expect(page.getByText(/1 требует повторения/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Рекомендации" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Вся история" }).click();
  await expect(page.getByText("Занятия: Тест")).toBeVisible();
  await page.getByRole("tab", { name: "Повторить" }).click();
  await expect(page.getByRole("link", { name: /7 \* 8/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /12 \* 4/ })).toHaveCount(0);
  await page.getByRole("link", { name: /7 \* 8/ }).click();

  await expect(page.getByText("Ответы ребёнка")).toBeVisible();
  await expect(page.getByText("Попытка 1")).toBeVisible();
  await expect(page.getByText("Переписка с помощником")).toBeVisible();
  await expect(page.getByText("Подсказка:").first()).toBeVisible();

  await page.goto(`/parent/children/${family.childId}/settings`);
  await expect(page.getByText("Родительский контроль")).toBeVisible();
  const switches = page.getByRole("switch");
  await expect(switches).toHaveCount(3);
  await switches.nth(0).click(); // transcript off
  await expect(page.getByText("Сохранено").first()).toBeVisible();
  await expect(switches.nth(0)).toHaveAttribute("aria-checked", "false");
  await switches.nth(1).click(); // photos off
  await expect(switches.nth(1)).toHaveAttribute("aria-checked", "false");

  await page.goto(`/parent/children/${family.childId}/sessions/${review}`);
  await expect(page.getByText("Показ переписки отключён")).toBeVisible();
  await expect(page.getByText("Ответы ребёнка")).toBeVisible();

  await page.goto("/parent/notifications");
  await expect(page.getByText("нужна помощь")).toBeVisible();
  await page.getByRole("button", { name: "Прочитать все" }).click();
  await expect(page.getByRole("button", { name: "Прочитать все" })).toHaveCount(
    0,
  );

  // the child's app mirrors the restriction and the backend enforces it
  await page.goto("/parent/settings");
  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(page.getByRole("button", { name: "Я ученик" })).toBeVisible();
  await loginAsChild(page, family.familyCode, family.nickname, family.pin);
  await expect(
    page.getByText("Родители отключили загрузку фото"),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Сфотографировать задание" }),
  ).toHaveCount(0);
  const blocked = await child.upload({ source: "camera" });
  expect(blocked.status()).toBe(403);
});
