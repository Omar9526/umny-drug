# «Умный друг» — проектные правила

Образовательный помощник для школьников (КР, ru/ky). Главный сценарий: фото задания → распознавание →
подтверждение → объяснение → вопросы → проверка ответа → история. Никаких XP, монет, рейтингов.
Бренд — «Умный друг» (без «AI» в названии). ТЗ и промпт: `docs/PROMPT.md`, референсы: `docs/reference/`.

## Запуск (эта машина: Windows, без Docker/Postgres/Redis)

- Корневой `.env` с `DEV_FALLBACK=1` (SQLite, eager Celery, locmem cache, локальное приватное
  хранилище). Никогда не включать в production.
- Backend: `backend/.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000`
  (venv уже создан; зависимости — `requirements-dev.txt`).
- Frontend: `cd frontend && npm run dev` → http://localhost:3000. API берётся из
  `NEXT_PUBLIC_API_URL` (`frontend/.env.local`).
- Логи dev-серверов писать в scratchpad, не в дерево проекта (Next.js watcher).
- Демо-семья в локальной dev-БД: родитель `demo@umnydrug.local` / `Demo-pass-2026`, код семьи `67J-8X7`, ребёнок Алина, PIN `2468`.
  Только для этой машины; в production таких учёток нет.
- Полный стек: `docker compose up --build` (не проверялось на этой машине).

## Проверки перед отчётом

```
cd backend && .venv/Scripts/python.exe -m pytest && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format --check .
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```
`npm run typecheck` требует сгенерированных типов маршрутов: после добавления маршрутов выполнить
`npx next typegen` (делается автоматически при `next dev`/`next build`).

## Конвенции

- Backend: бизнес-логика в `services.py`, views тонкие; все многошаговые записи в
  `transaction.atomic`. Ошибки API — только через `apps.core.exceptions` (единый формат
  `{"error": {code, message, details, request_id}}`). Доменные ошибки — `DomainError(code=..., status_code=...)`.
- Изоляция семей: каждая пользовательская модель имеет FK `family`; списки фильтруются через
  `FamilyScopedQuerysetMixin`, точечные выборки — через queryset, уже ограниченный семьёй
  (404 вместо 403, чтобы не раскрывать существование чужих объектов).
- Роли: `IsStudent`, `IsParent`, `IsAdminRole` из `apps.core.permissions`. Teacher зарезервирован.
- Чувствительные действия пишутся в `AuditLog` через `apps.core.audit.audit(...)`, без персональных данных.
- AI: только через `ai.registry.get_provider()`; все ответы модели валидируются pydantic-схемами
  из `ai/schemas.py`. Текст с фото — недоверенные данные. Demo-провайдер всегда помечает себя.
- Локализуемые поля каталога — пары `name_ru/name_ky`; в API отдаётся `name` по `context["lang"]`.
- Сид каталога — `manage.py seed_curriculum`, идемпотентный (`update_or_create` по slug). Данные в
  `apps/curriculum/seed_data.py`; кыргызские названия тем частично пустые — нужна вычитка носителем.
- Frontend: все запросы через `lib/api/client.ts` (`api<T>()`), состояние сервера — TanStack Query,
  формы — RHF + Zod v4 (`z.email()`, `{ error }`), тексты — только через next-intl (`messages/ru.json`,
  `messages/ky.json`; новые ключи добавлять в оба файла). Токен доступа — в памяти, refresh — cookie.
- Дизайн-токены в `src/app/globals.css` (Lime/Teal/Ivory/Sage/Ink/Line); только светлая тема; кнопки
  не ниже 44 px; базовый текст 16 px. `src/app/shadcn-base.css` — вендоренный базовый CSS shadcn
  (пакет `shadcn` в зависимостях не держим: конфликтует с peer-deps).
- shadcn/ui здесь на `@base-ui/react`: вместо `asChild` используется `render={<Link href=... />}`.
- Детям не показывать очки/рейтинги; аватары только из пресетов; фамилии не собирать.

## Этап 2: главный сценарий (готов)

- Поток: `apps/assignments` (upload → `services.enqueue_recognition` → Celery `recognize_upload_task` →
  `Assignment` на каждую задачу) → `confirm_assignment` → `apps/tutor.services.create_session` →
  `run_turn` (генератор SSE) → `check_answer` (SymPy или `provider.assess`) → `complete_session` →
  `apps/learning.services.apply_session_result`.
- В eager-режиме распознавание выполняется внутри POST `/assignments/upload/` (запрос ждёт модель); с брокером —
  в воркере после коммита. Файлы изображений читать через `with image.file.open("rb")`, иначе на Windows их нельзя удалить.
- SSE-view обязан объявлять `renderer_classes = (EventStreamRenderer, JSONRenderer)`, иначе DRF отвечает 406 на
  `Accept: text/event-stream`. Клиент — `features/tutor/api.ts::streamTurn` (fetch + ReadableStream, не EventSource).
- В тестах провайдер подменяется через `ai.registry.set_provider_override` (фикстура `fake_provider`);
  тесты потоков передают `HTTP_ACCEPT="text/event-stream"`.
- Контракт модели: ответ = markdown + `<meta>{json}</meta>`; меняя поля `TutorMeta`, обновить `ai/prompts/tutor.py`,
  `MessagePayload` в `frontend/src/lib/api/types.ts` и парсер `parse_turn`.
- Клиенту никогда не уходят `expected_answer` и `rubric` (`CLIENT_HIDDEN_PAYLOAD_KEYS` в `apps/tutor/serializers.py`);
  сессия завершается только по верному ответу с `is_final_answer=true`, промежуточный верный ответ → `continue_with: next_step`.
- `ai/verifiers/math.py`: строгая грамматика + `parse_expr` без builtins + daemon-поток с таймаутом 2 с. Любой
  «странный» ввод → `uncertain`, никогда не исключение и не зависание. Новые кейсы добавлять в `test_math_verifier.py`.
- Под ASGI (gunicorn+uvicorn) SSE отдаётся через async-обёртку (`sse_response(..., asgi=is_asgi(request))`); под
  `runserver` (WSGI) — синхронно. Не возвращать sync-генератор напрямую под ASGI: Django буферизует его целиком.
- Лимиты AI: глобальный `AI_DAILY_BUDGET_USD`, на семью `AI_DAILY_BUDGET_PER_FAMILY_USD`, на ребёнка
  `AI_DAILY_CALLS_PER_STUDENT`; все вызовы провайдера идут через `ensure_budget(student=, family=)`.
- E2E: `cd frontend && npm run test:e2e` (Playwright на системном Chrome, нужны запущенные backend и frontend).
- Экран сессии держит состояние в кэше TanStack (`setQueryData(["session", id])`), локально — только текст потока.

## Этап 3: кабинет родителя (готов)

- Все цифры кабинета считаются из реальных строк (`apps/parents/services.py`: `child_summary`, `subject_breakdown`,
  `weekly_report`, `recommendations`). Без данных API честно отдаёт нули и `has_data: false`; ничего не выдумывать.
- Уведомления родителю — `ParentNotification`: «нужна помощь» создаётся из `complete_session` только при исходе
  `needs_review` (дедупликация 24 ч по теме), недельный отчёт — beat-задача `send_weekly_reports` (понедельник 09:00),
  идемпотентна в пределах недели и уважает `notify_weekly_report`.
- Родительский контроль хранится в `StudentProfile` (`share_conversations_with_parent`, `allow_photo_upload`,
  `allow_free_questions`) и проверяется на сервере: upload с фото → 403 `feature_disabled`, режимы `question`/`check_answer`
  → 403; переписка в `GET /parents/children/{id}/sessions/{sid}/` отдаётся пустой при выключенном показе. UI ученика
  (home, capture, ask) только зеркалит флаги из `dashboard.student`.
- Удаление: `erase_child_data` стирает занятия/фото/прогресс и анонимизирует профиль; `delete_family` требует пароль,
  закрывает все аккаунты семьи и чистит refresh-cookie. Отзыв согласия `child_data`/`ai_processing` деактивирует ребёнка.
- Тесты backend идут на `config.settings_test`: лимиты — production-значения, провайдер всегда demo, ключ из `.env`
  не используется. Локальный `.env` может ослаблять `THROTTLE_AUTH`/`THROTTLE_CHILD_LOGIN` для повторных E2E.
- E2E-хелперы в `frontend/e2e/helpers.ts` (`createFamily`, `loginAsParent`, `loginAsChild`, `ChildApi`): данные для
  сценариев создаются через API, не через сиды.
- Общий queryset сессии — `apps/tutor/queries.py::session_queryset(detail=)`; и ученик, и родитель читают через него.

## Этап 4: предметы, карта знаний, викторины (готов)

- Карта знаний — `GET /api/v1/learning/map/?subject=<slug>[&student=]` (`apps/learning/services.py::knowledge_map`):
  узлы из `KnowledgeMapNode` (route_key `<subject>-<grade>`, x 0–100) со статусом из `LearningProgress`, `next_topic_id` =
  первый `needs_review` → `learning` → `not_started`. Для маршрутов без узлов строится zigzag по порядку тем.
- Викторины живут в `apps/quizzes` (заготовка этапа 1 + `services.py`): `POST quizzes/start/ {topic_id}` → незавершённая
  попытка возобновляется, иначе выдаётся непройденный Quiz или генерируется новый через `provider.generate_quiz`.
  Правильные ответы хранятся только в `Question.correct`; клиенту отдаётся `QuestionPublicSerializer` без них. Проверка —
  на сервере: `numeric` через `verify_math`, `single/multiple` по ключам, `text` по нормализованному списку допустимых.
- Demo-провайдер делает настоящие арифметические викторины (`ai/quiz_rules.py`, source `rules`, без расхода бюджета);
  для остальных предметов без ключа → `409 demo_mode`, UI честно объясняет. Для Claude — `QuizSpec` structured output,
  `AIUsage.purpose="quiz"`, `ensure_budget` перед генерацией.
- Итог викторины двигает статус темы (`apply_quiz_result`: ≥0.8 → completed/mastered, <0.5 → needs_review). Очков нет.
- Экран викторины (`/quizzes/[id]`): индекс вопроса — явное состояние `QuizRunner`, меняется только кнопками, иначе разбор
  ответа пропускается (баг, пойманный E2E). `/topics/[id]` — экран темы с действиями; `/subjects/[slug]` — карта + список.
- Родитель видит карту ребёнка (`/parent/children/[id]/map`, те же эндпоинты с `?student=`) и последние проверки в прогрессе.
- Сид программы покрывает 1–11 классы (597 тем, 223 раздела). Темы 10–11 классов (328) добавлены 2026-10-22 по типовой
  программе и ждут сверки учителем-предметником (список спорных мест — в отчёте этапа); `ky` у них пустые.

## Дизайн v2 (октябрь 2026) и провайдер Gemini

- Визуальный язык ученика повторяет референс `docs/reference/design_reference.png`: лаймовый full-bleed hero
  (`components/layout/Hero.tsx`, фон-контуры `Contours`), крупные заголовки шрифтом Onest (`--font-heading`),
  плитки предметов с линейными иллюстрациями (`components/brand/SubjectArt.tsx`, ключ = `Subject.icon`,
  `color=teal` → тёмная плитка), плавающая тёмно-бирюзовая навигация с «белой пилюлей» активной вкладки
  (`AppShell`, анимация `motion` `layoutId`). Шкала радиусов темы крупная (`rounded-2xl` = 32 px), поэтому
  у маленьких плиток радиусы заданы явно (`rounded-[16px]`), иначе они превращаются в круги.
- Карта знаний — «поле»: раздел = карточка-уровень, тема = нумерованная квадратная клетка со статусом;
  аватар ребёнка прыгает на следующей теме; тап по клетке открывает peek-панель (`role=dialog`) с действиями.
  Викторина: нумерованные клетки прогресса, ответы-пилюли, «Разбор:» с шагами, «Пропустить», конфетти на итоге.
  Очков и рейтингов по-прежнему нет (в референсе есть leaderboard — осознанно не реализован).
- E2E-селекторы карты: клетка `button[data-topic-id]` (aria-label `«Тема: Статус»`), в панели кнопка
  «Открыть тему»; в викторине `h2[data-question-prompt]`, варианты `[data-option-text]`.
- Провайдеры AI: `AI_PROVIDER=auto` → Anthropic (если есть `ANTHROPIC_API_KEY`) → Gemini (`GEMINI_API_KEY`) → demo.
  `ai/gemini_provider.py` (SDK `google-genai`): structured output через `response_schema`, стрим через
  `generate_content_stream`, общий парсер `<meta>` в `ai/turns.py`. Developer API не принимает `list[dict]` в
  схемах — для оценки используется `GeminiAssessment` с типизированными критериями. Модели: `GEMINI_MODEL`
  (объяснения, проверка, викторины; по умолчанию `gemini-3.5-flash`), `GEMINI_MODEL_VISION` (распознавание;
  `gemini-3.5-flash-lite`, ~2 с вместо 15–25 с). `gemini-2.5-*` недоступны новым ключам, `gemini-3.8-flash`
  дешевле, но медленнее и часто 503. `thinking_level=minimal` модели 3.x отклоняют — используем `low`.
- Распознавание фото: одна попытка ограничена 12 с (`RECOGNITION_TIMEOUT_S`), SDK повторяет до 3 раз — flash-lite
  обычно отвечает за 2–5 с, но иногда зависает на 30 с; после обрыва повтор отвечает за ~3 с. Если все попытки
  на flash-lite упали с retryable-ошибкой (таймаут, 5xx — 2026-10-22 Google отдавал 504 на все три подряд),
  делается один запрос на `GEMINI_MODEL` с лимитом 25 с (`RECOGNITION_FALLBACK_TIMEOUT_S`); отказ по содержимому
  (`refused`) не повторяется. Формулы в тексте
  заданий приходят в `$…$`, экраны выбора задания и подтверждения рендерят их через `Markdown` (KaTeX).
- Вызовы модели никогда не держат транзакцию: `start_quiz` генерирует викторину вне `atomic`, иначе SQLite в dev
  (и долгие блокировки в production) ловят «database is locked» на параллельных запросах.
- E2E-сценарии проверяют скриптовые ответы demo-провайдера и сами пропускаются (`skipUnlessDemo`), если бэкенд
  работает с реальной моделью. Скриншоты снимать через Playwright (`chromium.launch({ channel: "chrome" })`):
  Chrome 155 перестал открывать `--remote-debugging-port` для внешних CDP-скриптов.
- Локально ключ Gemini лежит в корневом `.env` (gitignored); в чат ключи не вставлять.
- После ревью 2026-10-22: `erase_child_data` атомарна, удаляет `Assignment` явно (FK upload — SET_NULL) и файлы через
  `on_commit`; `erase` доступен и для деактивированного ребёнка (`child_for_erase`); `erase`/`delete_family` под throttle
  `auth`. `start_quiz` держит cache-lock `quiz-start:<student>:<topic>` на время генерации (повтор → 409 `quiz_generating`),
  `_open_attempt` перепроверяет незавершённую попытку под `select_for_update`; старт под throttle `ai`; викторина без
  единого ответа не меняет статус темы; в результатах есть `correct_keys`. Родительский запрет свободных вопросов
  требует `topic_id` для explain_topic/exam_prep/practice. Оборванный SSE пишет строку `AIUsage` с model=`aborted`
  (лимит вызовов считает и её). Повтор загрузки ограничен `MAX_RETRIES=3` (`AssignmentUpload.retry_count`).
  Фото выдаются только самому ученику или родителю (не брату/сестре).

## Этап 5: безопасность, PWA, эксплуатация (в работе 2026-10-22)

- `ENVIRONMENT` без значения = production (fail closed); локально `.env` задаёт development. Тесты форсируют
  development в `settings_test.py`.
- Django admin требует 2FA (django-otp, TOTP) во всех окружениях: пароль + 6-значный код, обходов для dev нет.
  Включить: `manage.py admin_totp <email>` (staff) → otpauth URL/секрет в Google Authenticator/1Password;
  `--reset` перевыпускает ключ, `--qr` печатает QR (нужен пакет qrcode). Без аргументов — список staff и ключей.
  Форма и сообщения — `apps/accounts/admin_site.py`.
- Refresh-токен: повторное предъявление уже ротированного/отозванного токена позже
  `AUTH_REFRESH_REUSE_GRACE_SECONDS` (30 с, гонка вкладок) отзывает все сессии пользователя, чистит cookie,
  ответ 401 `session_revoked`, запись в audit `auth.refresh_reuse_detected`.
- Стирание данных ребёнка требует пароль родителя (`PasswordConfirmSerializer`), как и удаление семьи.
- Лимит вызовов на ученика резервируется атомарно в cache (`ai-calls:<день>:<student>`) до вызова модели;
  строки `AIUsage` остаются источником истины. Beat-задача `check_ai_budget` (раз в час) шлёт `mail_admins`
  при расходе ≥ `AI_BUDGET_ALERT_THRESHOLD`; сводка для операторов — `GET /api/v1/admin/ai-usage/` (admin).
- Frontend: CSP с nonce в `src/proxy.ts` (скрипты только с nonce, стили `'unsafe-inline'` из-за inline-атрибутов
  Tailwind/KaTeX, `connect-src`/`img-src` = origin API; в dev добавлены `'unsafe-eval'` и `ws:`), HSTS и COOP в
  `next.config.ts`. Новые внешние ресурсы нужно добавлять в CSP явно.
- PWA без плагинов: `public/sw.js` (кэши `ud-*` с `VERSION` — поднимать при смене правил; кэшируются только
  `/offline`, иконки и `/_next/static`; навигация network-first → `/offline`; `/api/*`, другой origin и RSC не
  кэшируются — страницы с данными ребёнка в кэш не попадают), `components/pwa/ServiceWorkerRegistration.tsx`
  (только production, тост «Доступно обновление»), `components/pwa/InstallPrompt.tsx` (beforeinstallprompt /
  подсказка iOS, «Позже» на 14 дней в localStorage), `app/offline/`. `sw.js` отдаётся с `no-store` и своим CSP.
  Язык офлайн-страницы фиксируется при установке SW (cookie `ud_locale`).
- Web Push родителям (2026-10-26): `apps/parents/push.py` (VAPID через `pywebpush`), модель `PushSubscription`
  (endpoint уникален; другой родитель, подписавший тот же телефон, забирает подписку себе; не больше
  `MAX_DEVICES_PER_PARENT=10` устройств, лишние — самые старые — удаляются). API: `GET parents/push/?endpoint_hash=<sha256>`
  → `enabled`, `public_key`, `devices`, `subscribed` (endpoint — capability-URL, в query и логи не попадает),
  `POST parents/push/subscriptions/` (201 новая/перехват, 200 обновление) и `DELETE` → `{deleted: n}`; throttle-scope `push`.
  Валидация при подписке: endpoint только `https://` и хост из `WEBPUSH_ALLOWED_HOSTS` (FCM/Mozilla/Apple/WNS — защита от SSRF),
  `p256dh` — точка P-256, `auth` — 16 байт. Все уведомления создаются только через `services.create_notification` →
  `push.schedule` → `on_commit(robust=True)` → Celery `send_push` → `push.deliver` (404/410 удаляют подписку; 4xx кроме 429
  копят `failures`, 5 подряд — удаление; 429/5xx/сеть не считаются; `deliver` никогда не бросает, неактивным родителям не шлёт).
  `revoke_user_sessions` (reuse refresh-токена, удаление семьи) удаляет и push-подписки. Ключи: `manage.py vapid_keys` →
  `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY`/`VAPID_SUBJECT` в `.env`; без них push выключен, системная проверка `parents.E001–E004`
  ловит рассинхрон пары. Frontend: `lib/push.ts` (браузер, `sha256Hex`, `hasServerKey`), `features/parent/push.ts`
  (`readPushState`/`enablePush`/`disablePush`/`resyncPush`/`forgetPushOnLogout`), тумблер `components/parent/PushToggle.tsx`
  в настройках семьи — «включено» только если сервер знает этот endpoint за текущим родителем; локально снимается только
  при `deleted > 0` (чужая подписка на общем телефоне переживает наш выход); `localStorage.ud_push_parent` = id родителя,
  включившего push на устройстве, — по нему `resyncPush` молча перерегистрирует подписку после `pushsubscriptionchange`.
  Logout родителя (не ребёнка) вызывает `forgetPushOnLogout` с таймаутом 3 с. `sw.js` v2: `push`, `notificationclick`
  (только same-origin URL), `pushsubscriptionchange`. В dev SW не регистрируется → тумблер показывает «не поддерживается»;
  проверять на `next build && next start` реальным Chrome (headless-Chrome без push-сервиса, incognito без Push API;
  профиль Playwright держать по короткому пути — длинный путь ломает CacheStorage и install SW на Windows).
  WebView обёртки Capacitor Web Push не получает — там нужен FCM/APNs (`@capacitor/push-notifications`).
- Деплой: `docs/DEPLOY.md`; мобильная обёртка: `docs/MOBILE.md`. Lock зависимостей: `backend/requirements.lock.txt`
  (снят с Windows-venv, с dev-пакетами; production-lock собрать в Linux-контейнере).
- По релизному аудиту 2026-10-22: `.dockerignore` в обоих сервисах; compose требует все секреты (`${VAR:?}`), не публикует
  порты хранилищ, backend/frontend только на 127.0.0.1, `NUM_PROXIES=1`, одноразовый сервис `migrate`, healthchecks и
  `restart: unless-stopped`, теги MinIO закреплены (проверить `docker compose pull`); фото всегда стримятся через API
  (presigned-URL ломал CSP и указывал на внутренний хост); `/health/` отдаёт 503 при деградации БД/кэша;
  `.env.production.example`; `scripts/backup_db.sh`. Юридические страницы — черновик с плейсхолдерами `[...]`,
  нужна юридическая вычитка до запуска. Dev-only: `X-Content-Type-Options` не ставится в dev (манифест прокси
  Turbopack отдаётся как JSON).
- Dev-сервер Next на этой машине иногда падает с паникой Turbopack «node process exited 0xc0000142» при компиляции
  CSS; лечится остановкой, `rm -rf frontend/.next/dev` и перезапуском. Production-сборка (`next build`/`next start`)
  при этом работает.

## Чего не делать

- Не выдавать Demo Mode за интеграцию AI; не класть ключи в репозиторий.
- Не добавлять `localStorage` для токенов.
- Не удалять данные детей без явного запроса родителя (деактивация + отзыв согласий, см. `deactivate_child`).
- Не ломать `/api/v1/` контракты без версии: мобильная обёртка (Capacitor) обновляется не сразу.
