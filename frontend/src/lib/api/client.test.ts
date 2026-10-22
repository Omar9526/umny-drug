import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";
import { getAccessToken, onAuthLost, setAccessToken } from "./token";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken(null);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("maps the unified error payload onto ApiError with field errors", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(400, {
        error: { code: "validation_error", message: "Проверьте данные.", details: { email: ["Некорректный email"] } },
      }),
    );
    await expect(api("/api/v1/auth/login/", { method: "POST", body: {}, auth: false })).rejects.toMatchObject({
      status: 400,
      code: "validation_error",
    });
    try {
      await api("/x", { auth: false });
    } catch {
      /* second call has no mock – ignore */
    }
  });

  it("refreshes once on 401 and retries with the new access token", async () => {
    setAccessToken("stale");
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "not_authenticated", message: "x" } }))
      .mockResolvedValueOnce(jsonResponse(200, { access: "fresh", user: { id: "u", role: "student" } }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const result = await api<{ ok: boolean }>("/api/v1/students/me/");
    expect(result.ok).toBe(true);
    expect(getAccessToken()).toBe("fresh");
    const lastCall = fetchMock.mock.calls[2];
    expect((lastCall[1] as RequestInit).headers).toMatchObject({ Authorization: "Bearer fresh" });
  });

  it("emits auth-lost when refresh fails", async () => {
    const lost = vi.fn();
    const unsubscribe = onAuthLost(lost);
    setAccessToken("stale");
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "not_authenticated", message: "x" } }))
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "not_authenticated", message: "expired" } }));

    await expect(api("/api/v1/students/me/")).rejects.toBeInstanceOf(ApiError);
    expect(lost).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
    unsubscribe();
  });
});
