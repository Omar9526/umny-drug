# Мобильные приложения: PWA сейчас, Capacitor потом

## Сейчас: PWA

Приложение устанавливается на телефон из браузера: `manifest.webmanifest`, иконки, service worker
(`frontend/public/sw.js`), офлайн-страница `/offline`, баннер «Установить приложение» на главных экранах.
Service worker кэширует только оболочку и статику; страницы с данными ребёнка и ответы API не кэшируются.
Камера работает через `<input capture>`. Уведомления родителю приходят внутри приложения и как Web Push
(тумблер «Push на это устройство» в настройках семьи): Android и десктоп — прямо из браузера, iOS 16.4+ — только
после установки на экран «Домой». Серверу нужны VAPID-ключи (`manage.py vapid_keys`), см. `docs/DEPLOY.md`.

## Потом: обёртка Capacitor (iOS / Android)

Next.js здесь рендерится на сервере, поэтому Capacitor должен работать в режиме удалённого URL, а не
статического экспорта:

```ts
// capacitor.config.ts (создаётся в frontend/ командой `npx cap init`)
const config = {
  appId: "kg.umnydrug.app",
  appName: "Умный друг",
  webDir: "public",                 // формально обязателен, реально не используется
  server: { url: "https://app.example.kg", cleartext: false },
};
export default config;
```

Что нужно сделать на этом шаге:

1. Проверить вход: refresh-cookie `SameSite=Lax` при origin `capacitor://localhost` / `https://localhost`
   не отправляется. Варианты: открывать приложение по тому же домену (`server.url`, как выше — тогда cookie
   обычные) или добавить обмен refresh-токена через `@capacitor/preferences` только для нативной обёртки.
2. Камера: `@capacitor/camera` вместо `<input capture>` (качество фото и разрешения).
3. Push-уведомления родителям: WebView обёртки Web Push не получает, нужен `@capacitor/push-notifications`
   (FCM для Android, APNs для iOS — внешние проекты Firebase/Apple) и расширение `PushSubscription`/`push.deliver`
   под нативные токены. До этого push работает только в PWA.
4. Магазины: политика конфиденциальности (`/legal/privacy`), возрастная категория, Apple «Kids Category»
   требует отсутствие трекинга и рекламы — в приложении их нет.
5. CSP: добавить `capacitor://localhost` в `connect-src`/`img-src`, если обёртка не использует `server.url`.

Контракт `/api/v1/` не ломать без версии: нативные приложения обновляются не сразу.
