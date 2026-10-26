# Мобильные приложения: PWA сейчас, Capacitor потом

## Сейчас: PWA

Приложение устанавливается на телефон из браузера: `manifest.webmanifest`, иконки, service worker
(`frontend/public/sw.js`), офлайн-страница `/offline`, баннер «Установить приложение» на главных экранах.
Service worker кэширует только оболочку и статику; страницы с данными ребёнка и ответы API не кэшируются.
Камера работает через `<input capture>`. Уведомления родителю приходят внутри приложения и как Web Push
(тумблер «Push на это устройство» в настройках семьи): Android и десктоп — прямо из браузера, iOS 16.4+ — только
после установки на экран «Домой». Серверу нужны VAPID-ключи (`manage.py vapid_keys`), см. `docs/DEPLOY.md`.

## Обёртка Capacitor (Android готов как проект, iOS — на Mac)

Next.js рендерится на сервере, поэтому обёртка работает в режиме удалённого URL, а не статического экспорта:
WebView открывает развёрнутый сайт, cookies остаются first-party, API-контракт тот же. Конфигурация —
`frontend/capacitor.config.ts` (`appId` `kg.umnydrug.app`, имя «Умный друг»); адрес берётся из переменной
`CAPACITOR_SERVER_URL` (по умолчанию `https://app.example.kg` — заменить на реальный домен). Для проверки на
телефоне в одной Wi-Fi можно указать `http://<ip-ноутбука>:3000`: cleartext тогда разрешается автоматически.

Android-проект сгенерирован командой `npx cap add android` и лежит в `frontend/android/` (Capacitor 8).
Сборка на машине разработки не проверялась: нужны JDK 17+ и Android Studio (Android SDK).

```bash
cd frontend
CAPACITOR_SERVER_URL=https://app.<домен> npx cap sync android   # копирует public/ и capacitor.config.json
npx cap open android                                            # Android Studio → Build → APK / AAB
```

iOS добавляется на Mac: `npx cap add ios && npx cap sync ios && npx cap open ios` (нужны Xcode и CocoaPods);
пакет `@capacitor/ios` уже в зависимостях. Папки `android/` и `ios/` исключены из ESLint и Docker-образа.

Что ещё нужно до публикации:

1. Камера: `@capacitor/camera` вместо `<input capture>` (качество фото и разрешения).
2. Иконки и splash: `npx @capacitor/assets generate` из `public/icons/`.
3. Push-уведомления родителям: WebView обёртки Web Push не получает, нужен `@capacitor/push-notifications`
   (FCM для Android, APNs для iOS — внешние проекты Firebase/Apple) и расширение `PushSubscription`/`push.deliver`
   под нативные токены. До этого push работает только в PWA.
4. Магазины: политика конфиденциальности (`/legal/privacy`), возрастная категория, Apple «Kids Category»
   требует отсутствие трекинга и рекламы — в приложении их нет.
5. CSP менять не нужно, пока обёртка использует `server.url`; при переходе на локальные ассеты добавить
   `capacitor://localhost` в `connect-src`/`img-src`.

Контракт `/api/v1/` не ломать без версии: нативные приложения обновляются не сразу.
