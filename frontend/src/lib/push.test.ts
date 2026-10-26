import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { detectPushSupport, hasServerKey, sha256Hex, urlBase64ToUint8Array } from "./push";

const IPHONE_SAFARI =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

describe("urlBase64ToUint8Array", () => {
  it("decodes base64url with or without padding", () => {
    expect(Array.from(urlBase64ToUint8Array("AQID"))).toEqual([1, 2, 3]);
    expect(Array.from(urlBase64ToUint8Array("AQI"))).toEqual([1, 2]);
    expect(Array.from(urlBase64ToUint8Array("-_8"))).toEqual([0xfb, 0xff]);
  });
});

describe("sha256Hex", () => {
  it("matches the backend's hashlib.sha256().hexdigest()", async () => {
    expect(await sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
});

describe("hasServerKey", () => {
  const subscriptionFor = (key: Uint8Array | null) =>
    ({ options: { applicationServerKey: key ? key.buffer : null } }) as unknown as PushSubscription;

  it("compares the subscription's key with the server key byte by byte", () => {
    expect(hasServerKey(subscriptionFor(Uint8Array.from([1, 2, 3])), "AQID")).toBe(true);
    expect(hasServerKey(subscriptionFor(Uint8Array.from([1, 2, 4])), "AQID")).toBe(false);
    expect(hasServerKey(subscriptionFor(null), "AQID")).toBe(false);
  });
});

describe("detectPushSupport", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    Reflect.deleteProperty(navigator, "serviceWorker");
  });

  function enableApis(permission: NotificationPermission) {
    Object.defineProperty(navigator, "serviceWorker", { value: {}, configurable: true });
    vi.stubGlobal("PushManager", class {});
    vi.stubGlobal("Notification", { permission });
  }

  it("tells iOS Safari in a browser tab to install the app first", () => {
    vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(IPHONE_SAFARI);
    expect(detectPushSupport()).toBe("needs-install");
  });

  it("reports plain unsupported browsers", () => {
    expect(detectPushSupport()).toBe("unsupported");
  });

  it("distinguishes denied permission from a usable setup", () => {
    enableApis("denied");
    expect(detectPushSupport()).toBe("denied");
    enableApis("default");
    expect(detectPushSupport()).toBe("ready");
  });
});
