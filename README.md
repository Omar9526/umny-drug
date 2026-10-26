# Умный друг

**Твой умный друг по учёбе.** Образовательный помощник для школьников 1–11 классов и их родителей:
ребёнок фотографирует задание, получает пошаговое объяснение, отвечает сам и получает проверку;
родитель видит реальную учебную историю.

Первый рынок: Кыргызская Республика. Языки: русский и кыргызский.

## Статус

| Этап | Содержание | Состояние |
|---|---|---|
| 1 | Инфраструктура, дизайн-система, аккаунты (родитель / ребёнок), каталог программы, Dashboard | ✅ готов |
| 2 | Фото → распознавание → подтверждение → объяснение → диалог → проверка → история | ✅ готов |
| 3 | Кабинет родителя на реальных данных, отчёты, согласия | ✅ |
| 4 | Каталог предметов, карта знаний, викторины | ✅ |
| 5 | PWA (офлайн, установка, Web Push родителям), CSP/HSTS, 2FA админки, защита refresh-токена, алерты расходов AI, деплой-документация, Android-обёртка Capacitor (проект, сборка требует Android Studio) | ✅ готов |

Поддерживаются два провайдера: Claude (`ANTHROPIC_API_KEY`) и Gemini (`GEMINI_API_KEY`, SDK `google-genai`).
Без ключа AI-провайдера backend работает в явно помеченном **Demo Mode**: баннер в интерфейсе,
флаг `demo_mode` в `/api/v1/meta/`. Это не «интеграция AI».

## Стек

- **Frontend:** Next.js 16 (App Router), React 19, TypeScript strict, Tailwind CSS 4, shadcn/ui,
  TanStack Query, React Hook Form + Zod, next-intl (ru/ky), Lucide, PWA manifest.
- **Backend:** Django 5.2 LTS, Django REST Framework, SimpleJWT, drf-spectacular (OpenAPI),
  Celery, PostgreSQL, Redis, S3-совместимое хранилище, SymPy, Anthropic SDK.
- **Инфраструктура:** Docker Compose (postgres, redis, minio, backend, worker, beat, frontend).

## Быстрый старт (локально, без Docker)

На машине без Docker/PostgreSQL используется **dev fallback**: SQLite, eager Celery, локальное
приватное хранилище. Он запрещён при `ENVIRONMENT=production`.

```bash
cp .env.example .env            # DEV_FALLBACK=1 уже выставлен в примере

# backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # Windows; на *nix — .venv/bin/pip
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_curriculum        # каталог программы КР (идемпотентно)
.venv/Scripts/python manage.py createsuperuser        # для /admin/
.venv/Scripts/python manage.py runserver 127.0.0.1:8000

# frontend (второй терминал)
cd frontend
npm install
npm run dev                                           # http://localhost:3000
```

Полезные адреса: `http://localhost:8000/api/docs/` (Swagger), `http://localhost:8000/admin/`.

## Полный стек через Docker Compose

```bash
cp .env.example .env   # задайте DJANGO_SECRET_KEY, пароли Postgres/MinIO, ANTHROPIC_API_KEY или GEMINI_API_KEY
docker compose up --build
```

Backend сам применяет миграции и сид каталога при старте.

## Деплой и мобильные приложения

`docs/DEPLOY.md` — переменные окружения, первый запуск, reverse proxy, 2FA админки, beat-задачи, бэкапы.
`docs/MOBILE.md` — что уже даёт PWA и как завернуть в Capacitor.
`docs/HANDOFF.md` — промпт и шаги, чтобы продолжить разработку с другой машины.

## Проверки

```bash
# backend
cd backend && .venv/Scripts/python -m pytest && .venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .
# frontend
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
# E2E (Playwright на системном Chrome; нужны запущенные backend и frontend)
cd frontend && npm run test:e2e
```

Повторные E2E-прогоны упираются в лимит входа (10 запросов в минуту с одного IP). Для локальной
разработки в корневом `.env` можно задать `THROTTLE_AUTH=120/min` и `THROTTLE_CHILD_LOGIN=60/min`;
в production оставляйте значения по умолчанию.

## Как входят пользователи

- **Родитель:** email + пароль. После регистрации получает **код семьи** (6 символов) и добавляет детей.
- **Ребёнок:** вводит код семьи → выбирает себя → вводит PIN (4–6 цифр). После 5 неверных PIN —
  блокировка на 15 минут; попытки по коду семьи ограничены по IP.
- Токены: access (15 мин) живёт только в памяти клиента, refresh — HttpOnly cookie с ротацией и
  blacklist.

## Структура

```
backend/
  config/            настройки, urls, celery
  apps/
    core/            базовые модели, единый формат ошибок, request-id, аудит, permissions, throttles
    accounts/        User, Family, ParentProfile, StudentProfile, ParentStudentLink, ConsentRecord, auth API
    curriculum/      Curriculum, Grade, Subject, Section, Topic + seed_curriculum
    assignments/     AssignmentUpload, AssignmentImage, Assignment
    tutor/           LearningSession, AIConversation, AIMessage, SolutionStep
    learning/        AnswerAttempt, VerificationResult, LearningProgress, KnowledgeMapNode, история
    quizzes/         Quiz, Question, QuizAttempt
    parents/         ParentNotification, API кабинета родителя
    billing/         Subscription, Payment (модели; платежей в MVP нет)
  ai/                контракт провайдера, pydantic-схемы, Demo, Anthropic и Gemini провайдеры
frontend/src/
  app/               маршруты: (auth), (student), (parent), legal, admin
  components/        ui (shadcn), brand, layout, forms, feedback, cards
  features/          auth, dashboard, curriculum, parent — API-хуки
  lib/api/           fetch-клиент с авто-refresh, типы DTO
  messages/          ru.json, ky.json
docs/                ТЗ, промпт, референсы дизайна
```

## AI-слой

- `backend/ai/registry.py` выбирает провайдера (`AI_PROVIDER=auto`): `anthropic` при наличии `ANTHROPIC_API_KEY`,
  иначе `gemini` при наличии `GEMINI_API_KEY`, иначе `demo`. Для Gemini модели задаются `GEMINI_MODEL`
  (объяснения/проверка/викторины, по умолчанию `gemini-3.5-flash`) и `GEMINI_MODEL_VISION` (распознавание,
  `gemini-3.5-flash-lite`); цены для учёта расходов — в `ai/costs.py` (`AI_PRICING_JSON` переопределяет).
- `AnthropicProvider`: распознавание и оценка открытых ответов — структурированный вывод (`messages.parse` + pydantic);
  объяснение — потоковый `beta.messages.stream` с серверными fallback-моделями при отказе; хвост `<meta>{json}</meta>`
  валидируется схемой `TutorMeta`.
- Проверка ответов: числа и выражения — независимо через SymPy (`ai/verifiers/math.py`), открытые ответы — по критериям
  моделью, в демо — честный «не удалось проверить».
- Стоимость: каждая модель-операция пишется в `AIUsage`; `AI_DAILY_BUDGET_USD` останавливает новые запросы при превышении.
- Модели задаются в `.env` (`AI_MODEL_TUTOR` и др.), по умолчанию `claude-opus-5-5`; `claude-sonnet-5-5` дешевле.
- Поток объяснения: `POST /api/v1/tutor/sessions/{id}/messages/` → Server-Sent Events (`delta` → `final` | `error`).

## Безопасность данных детей

Минимум персональных данных (псевдоним, класс, язык; аватары только из набора), изоляция семей на
уровне запросов к БД, версионируемые и отзываемые согласия, приватное хранилище файлов без публичных
URL, ограничение срока хранения изображений, аудит чувствительных действий, единый формат ошибок без
утечки внутренностей. До публичного запуска требуется юридическая проверка по законодательству КР.

## Кабинет родителя (этап 3)

Все цифры считаются из сохранённых занятий, попыток и прогресса; без данных кабинет честно показывает нули.

- `GET /api/v1/parents/overview/` — дети с недельной сводкой, непрочитанные уведомления, код семьи.
- `GET /api/v1/parents/children/{id}/progress/` — недельный отчёт (текст + цифры), рекомендации по правилам,
  разбивка по предметам, сложные темы, последние занятия.
- `GET /api/v1/parents/children/{id}/sessions/[{sid}/]` — история и детали занятия; переписка видна только если
  в профиле ребёнка включён показ (`share_conversations_with_parent`), итоги и ответы — всегда.
- `PATCH /api/v1/parents/children/{id}/` — профиль и родительский контроль (`allow_photo_upload`,
  `allow_free_questions`); ограничения применяются на сервере.
- `POST /api/v1/parents/children/{id}/erase/`, `POST /api/v1/parents/family/delete/` — удаление данных ребёнка
  и всей семьи (с паролем). `GET/POST /api/v1/parents/consents/…/revoke/` — согласия и их отзыв.
- Уведомления: `GET /api/v1/parents/notifications/`, `POST …/{id}/read/`, `POST …/read-all/`. «Нужна помощь»
  создаётся при исходе «повторить», недельный отчёт — Celery beat по понедельникам.

## Карта знаний и викторины (этап 4)

- `GET /api/v1/learning/map/?subject=math` — маршрут по предмету для класса ученика: статус каждой темы из реальной
  истории, следующий шаг, сводка. Родитель смотрит карту ребёнка с `&student=<id>`.
- `GET /api/v1/topics/{id}/` — тема с блоком прогресса, последней проверкой и занятиями по теме.
- Викторины: `POST /api/v1/quizzes/start/ {topic_id}` → `POST …/attempts/{id}/answer/ {question_id, answer}` →
  `POST …/attempts/{id}/finish/`. Ответы проверяются на сервере; правильные ответы до ответа не отдаются.
  Без AI-ключа викторины доступны только по математике (генератор арифметики), остальные предметы сообщают,
  что нужен провайдер.
