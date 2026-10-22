import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

export const API = process.env.E2E_API_URL ?? "http://localhost:8000";

export interface Family {
  email: string;
  password: string;
  familyCode: string;
  nickname: string;
  pin: string;
  childId: string;
  parentAccess: string;
}

/** Creates a fresh family through the real API so tests never depend on seeded demo data. */
export async function createFamily(
  request: APIRequestContext,
): Promise<Family> {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  const password = "E2e-Strong-Pass-2026";
  const reg = await request.post(`${API}/api/v1/auth/parent/register/`, {
    data: {
      display_name: "Родитель E2E",
      email,
      password,
      preferred_language: "ru",
      consents: { terms: true, privacy: true, marketing: false },
    },
  });
  expect(reg.ok(), await reg.text()).toBeTruthy();
  const body = await reg.json();
  const parentAccess = body.access as string;
  const familyCode = body.user.parent.family.code as string;
  const grades = await (await request.get(`${API}/api/v1/curricula/`)).json();
  const grade5 = grades[0].grades.find(
    (g: { number: number }) => g.number === 5,
  ).id;
  const child = await request.post(`${API}/api/v1/parents/children/`, {
    headers: { Authorization: `Bearer ${parentAccess}` },
    data: {
      nickname: "Тест",
      grade_id: grade5,
      instruction_language: "ru",
      explanation_language: "ru",
      avatar: "robot",
      pin: "2468",
      consent_confirmed: true,
    },
  });
  expect(child.ok(), await child.text()).toBeTruthy();
  const childId = (await child.json()).id as string;
  return {
    email,
    password,
    familyCode,
    nickname: "Тест",
    pin: "2468",
    childId,
    parentAccess,
  };
}

export async function loginAsChild(
  page: Page,
  familyCode: string,
  nickname: string,
  pin: string,
) {
  await page.goto("/child-login");
  await page.getByLabel("Введи код семьи").fill(familyCode);
  await page.getByRole("button", { name: "Найти семью" }).click();
  await page.getByRole("button", { name: nickname }).click();
  await page.locator("#pin").fill(pin);
  await page.getByRole("button", { name: "Войти" }).click();
  // first login → onboarding, later logins → home
  await page.waitForURL(/\/(onboarding|home)/);
  if (/\/onboarding/.test(page.url())) {
    await page.getByRole("button", { name: "Поехали!" }).click();
  }
  await expect(page).toHaveURL(/\/home/);
  await expect(page.getByRole("heading", { name: "С каким заданием помочь?" })).toBeVisible();
}

export async function loginAsParent(
  page: Page,
  email: string,
  password: string,
) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page).toHaveURL(/\/parent$/);
}

/** Child API session: the child solves tasks without the UI so parent tests have real data. */
export class ChildApi {
  constructor(
    private readonly request: APIRequestContext,
    private readonly token: string,
  ) {}

  static async login(
    request: APIRequestContext,
    family: Family,
  ): Promise<ChildApi> {
    const res = await request.post(`${API}/api/v1/auth/child/login/`, {
      data: {
        family_code: family.familyCode,
        student_id: family.childId,
        pin: family.pin,
      },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    return new ChildApi(request, (await res.json()).access as string);
  }

  private headers(extra: Record<string, string> = {}) {
    return { Authorization: `Bearer ${this.token}`, ...extra };
  }

  /** Typed task → confirm → first streamed explanation. Returns the session id. */
  async typedTask(text: string): Promise<string> {
    const upload = await this.request.post(
      `${API}/api/v1/assignments/upload/`,
      {
        headers: this.headers(),
        multipart: { source: "text", typed_text: text },
      },
    );
    expect(upload.ok(), await upload.text()).toBeTruthy();
    const taskId = (await upload.json()).tasks[0].id as string;
    const confirmed = await this.request.post(
      `${API}/api/v1/assignments/${taskId}/confirm/`,
      {
        headers: this.headers(),
        data: { confirmed_text: text },
      },
    );
    expect(confirmed.ok(), await confirmed.text()).toBeTruthy();
    const sessionId = (await confirmed.json()).session.id as string;
    await this.turn(sessionId, "start", text);
    return sessionId;
  }

  async turn(sessionId: string, command: string, content = "") {
    const res = await this.request.post(
      `${API}/api/v1/tutor/sessions/${sessionId}/messages/`,
      {
        headers: this.headers({ Accept: "text/event-stream" }),
        data: { command, content },
      },
    );
    expect(res.ok(), await res.text()).toBeTruthy();
    await res.text();
  }

  async checkAnswer(sessionId: string, answer: string) {
    const res = await this.request.post(
      `${API}/api/v1/tutor/sessions/${sessionId}/check-answer/`,
      {
        headers: this.headers(),
        data: { answer_text: answer },
      },
    );
    expect(res.ok(), await res.text()).toBeTruthy();
    return res.json();
  }

  /** Raw upload call, for asserting server-side restrictions. */
  upload(multipart: Record<string, string>) {
    return this.request.post(`${API}/api/v1/assignments/upload/`, {
      headers: this.headers(),
      multipart,
    });
  }

  async complete(sessionId: string) {
    const res = await this.request.post(
      `${API}/api/v1/tutor/sessions/${sessionId}/complete/`,
      {
        headers: this.headers(),
        data: {},
      },
    );
    expect(res.ok(), await res.text()).toBeTruthy();
    return res.json();
  }
}

/**
 * The E2E scenarios assert the scripted outputs of the Demo provider (and solve its rules-based
 * maths quizzes). With a real model configured (Gemini/Claude) they are skipped instead of failing
 * on non-deterministic text.
 */
export async function skipUnlessDemo(request: APIRequestContext) {
  const meta = await (await request.get(`${API}/api/v1/meta/`)).json();
  test.skip(
    !meta.demo_mode,
    `backend runs the real "${meta.ai_provider}" provider; demo-only scenario`,
  );
}
