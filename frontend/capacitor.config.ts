import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Native shells (Android/iOS) load the deployed web app in remote-URL mode: Next.js renders on the server,
 * there is no static export. `CAPACITOR_SERVER_URL` is the public https origin of the frontend; while
 * developing, a phone on the same Wi-Fi can point at the laptop (`http://<laptop-ip>:3000`), and cleartext
 * is then allowed automatically. Cookies stay first-party because the WebView browses the real origin.
 * See docs/MOBILE.md.
 */
const serverUrl = process.env.CAPACITOR_SERVER_URL ?? "https://app.example.kg";

const config: CapacitorConfig = {
  appId: "kg.umnydrug.app",
  appName: "Умный друг",
  // Required by the CLI; in remote-URL mode only the icons from here end up in the native bundle.
  webDir: "public",
  server: {
    url: serverUrl,
    cleartext: serverUrl.startsWith("http://"),
  },
  android: {
    allowMixedContent: false,
  },
};

export default config;
