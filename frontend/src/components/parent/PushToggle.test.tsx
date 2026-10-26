import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import messages from "@/messages/ru.json";
import { disablePush, enablePush, readPushState, resyncPush } from "@/features/parent/push";
import { detectPushSupport } from "@/lib/push";
import type { PushConfig } from "@/lib/api/types";
import { PushToggle } from "./PushToggle";

vi.mock("@/lib/push", () => ({ detectPushSupport: vi.fn() }));
vi.mock("@/features/parent/push", () => ({
  enablePush: vi.fn(),
  disablePush: vi.fn(),
  readPushState: vi.fn(),
  resyncPush: vi.fn(),
}));
vi.mock("@/features/auth/AuthProvider", () => ({ useAuth: () => ({ user: { id: "parent-1", role: "parent" } }) }));

const texts = messages.parent.family;
const PUBLIC_KEY = "BExampleServerKey";

function config(overrides: Partial<PushConfig> = {}): PushConfig {
  return { enabled: true, public_key: PUBLIC_KEY, devices: 0, subscribed: false, ...overrides };
}

function renderToggle() {
  return render(
    <NextIntlClientProvider locale="ru" messages={messages}>
      <PushToggle />
    </NextIntlClientProvider>,
  );
}

const fakeSubscription = { endpoint: "https://fcm.googleapis.com/fcm/send/abc" } as unknown as PushSubscription;

// base-ui's Switch is not a form control: its disabled state is exposed through `data-disabled`.
const expectInteractive = (el: HTMLElement) => expect(el).not.toHaveAttribute("data-disabled");
const expectBlocked = (el: HTMLElement) => expect(el).toHaveAttribute("data-disabled");

describe("PushToggle", () => {
  beforeEach(() => {
    vi.mocked(detectPushSupport).mockReturnValue("ready");
    vi.mocked(readPushState).mockResolvedValue({ config: config(), subscription: null });
    vi.mocked(resyncPush).mockResolvedValue(false);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("explains unsupported browsers and keeps the switch disabled", async () => {
    vi.mocked(detectPushSupport).mockReturnValue("unsupported");
    renderToggle();
    expect(await screen.findByText(texts.pushUnsupported)).toBeInTheDocument();
    expectBlocked(screen.getByRole("switch"));
    expect(readPushState).not.toHaveBeenCalled();
  });

  it("says so when the server has no VAPID keys", async () => {
    vi.mocked(readPushState).mockResolvedValue({
      config: config({ enabled: false, public_key: null }),
      subscription: null,
    });
    renderToggle();
    expect(await screen.findByText(texts.pushServerOff)).toBeInTheDocument();
    expectBlocked(screen.getByRole("switch"));
  });

  it("enables push for this device with the server key and the parent's id", async () => {
    vi.mocked(enablePush).mockResolvedValue("enabled");
    renderToggle();
    const toggle = screen.getByRole("switch");
    await waitFor(() => expectInteractive(toggle));
    expect(toggle).toHaveAttribute("aria-checked", "false");

    await userEvent.click(toggle);

    expect(enablePush).toHaveBeenCalledWith(PUBLIC_KEY, "parent-1");
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
  });

  it("shows the browser-denied hint when permission is refused", async () => {
    vi.mocked(enablePush).mockResolvedValue("denied");
    renderToggle();
    const toggle = screen.getByRole("switch");
    await waitFor(() => expectInteractive(toggle));
    await userEvent.click(toggle);
    expect(await screen.findByText(texts.pushDenied)).toBeInTheDocument();
    expectBlocked(toggle);
  });

  it("stays off and usable when the permission prompt is simply closed", async () => {
    vi.mocked(enablePush).mockResolvedValue("dismissed");
    renderToggle();
    const toggle = screen.getByRole("switch");
    await waitFor(() => expectInteractive(toggle));
    await userEvent.click(toggle);
    await waitFor(() => expectInteractive(toggle));
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText(texts.pushNotifyHint)).toBeInTheDocument();
  });

  it("is on only when the server knows this endpoint for this parent, and can be turned off", async () => {
    vi.mocked(readPushState).mockResolvedValue({
      config: config({ devices: 1, subscribed: true }),
      subscription: fakeSubscription,
    });
    vi.mocked(disablePush).mockResolvedValue();
    renderToggle();
    const toggle = screen.getByRole("switch");
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));

    await userEvent.click(toggle);

    expect(disablePush).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "false"));
  });

  it("re-registers a rotated subscription for the parent who enabled push here", async () => {
    const state = { config: config(), subscription: fakeSubscription };
    vi.mocked(readPushState).mockResolvedValue(state);
    vi.mocked(resyncPush).mockResolvedValue(true);
    renderToggle();
    const toggle = screen.getByRole("switch");
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
    expect(resyncPush).toHaveBeenCalledWith(state, "parent-1");
  });

  it("treats a subscription left by someone else as off", async () => {
    vi.mocked(readPushState).mockResolvedValue({ config: config(), subscription: fakeSubscription });
    renderToggle();
    const toggle = screen.getByRole("switch");
    await waitFor(() => expectInteractive(toggle));
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(enablePush).not.toHaveBeenCalled();
  });
});
