import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import messages from "@/messages/ru.json";
import { INSTALL_DISMISSED_KEY, InstallPrompt } from "./InstallPrompt";

const IPHONE_SAFARI =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

function renderPrompt() {
  return render(
    <NextIntlClientProvider locale="ru" messages={messages}>
      <InstallPrompt />
    </NextIntlClientProvider>,
  );
}

function fireBeforeInstallPrompt(outcome: "accepted" | "dismissed" = "accepted") {
  const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome, platform: "web" }),
  });
  act(() => {
    window.dispatchEvent(event);
  });
  return event;
}

describe("InstallPrompt", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders nothing until the browser offers installation", () => {
    renderPrompt();
    expect(screen.queryByText("Установить приложение")).not.toBeInTheDocument();
  });

  it("shows the banner on beforeinstallprompt and runs the native prompt", async () => {
    renderPrompt();
    const event = fireBeforeInstallPrompt();
    expect(event.defaultPrevented).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Установить" }));
    expect(event.prompt).toHaveBeenCalledOnce();
    expect(screen.queryByText("Установить приложение")).not.toBeInTheDocument();
  });

  it("remembers «Позже» for 14 days", async () => {
    renderPrompt();
    fireBeforeInstallPrompt();
    await userEvent.click(screen.getByRole("button", { name: "Позже" }));
    expect(screen.queryByText("Установить приложение")).not.toBeInTheDocument();
    const until = Number(window.localStorage.getItem(INSTALL_DISMISSED_KEY));
    expect(until - Date.now()).toBeGreaterThan(13.9 * 24 * 3600 * 1000);

    cleanup();
    renderPrompt();
    fireBeforeInstallPrompt();
    expect(screen.queryByText("Установить приложение")).not.toBeInTheDocument();
  });

  it("survives unavailable localStorage", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    renderPrompt();
    fireBeforeInstallPrompt();
    await userEvent.click(screen.getByRole("button", { name: "Позже" }));
    expect(screen.queryByText("Установить приложение")).not.toBeInTheDocument();
  });

  it("shows the Share → Home Screen hint on iOS Safari", () => {
    vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(IPHONE_SAFARI);
    renderPrompt();
    expect(screen.getByText("Нажми «Поделиться», затем «На экран „Домой“».")).toBeInTheDocument();
  });

  it("stays hidden when already running as an installed app", () => {
    vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(IPHONE_SAFARI);
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    renderPrompt();
    fireBeforeInstallPrompt();
    expect(screen.queryByText("Установить приложение")).not.toBeInTheDocument();
  });
});
