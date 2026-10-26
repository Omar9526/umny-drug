# Развёртывание «Умного друга»

Production описан в `docker-compose.yml`: одноразовый `migrate` (миграции + сид каталога), `backend` (Django +
gunicorn/uvicorn), `worker` и `beat` (Celery), `frontend` (Next.js standalone), `db` (Postgres), `redis`, `minio`
(или внешний S3). Все секреты обязательны (`${VAR:?}`), порты backend/frontend привязаны к 127.0.0.1, хранилища
наружу не публикуются. Шаблон переменных без dev-значений — `.env.production.example`.
Снаружи — reverse proxy с TLS (Caddy или nginx), который отдаёт `app.<домен>` → frontend:3000 и
`api.<домен>` → backend:8000.

## 1. Переменные окружения

Скопируйте `.env.production.example` в `.env` на сервере и заполните. Обязательные для production:

| Переменная | Зачем |
|---|---|
| `ENVIRONMENT=production` | включает все production-guard'ы (без него — тоже production, но лучше явно) |
| `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY` | случайные строки ≥ 50 символов, разные |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | домены API и приложения |
| `DATABASE_URL`, `REDIS_URL` | Postgres и Redis |
| `STORAGE_BACKEND=s3`, `S3_*` | приватное хранилище фото заданий (MinIO или S3) |
| `GEMINI_API_KEY` **или** `ANTHROPIC_API_KEY` | провайдер AI; `AI_PROVIDER=auto` выбирает Anthropic → Gemini → demo |
| `AI_DAILY_BUDGET_USD`, `AI_DAILY_BUDGET_PER_FAMILY_USD`, `AI_DAILY_CALLS_PER_STUDENT` | лимиты расходов |
| `DJANGO_ADMINS`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | письма-алерты о расходах AI |
| `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT` | Web Push родителям; пара из `manage.py vapid_keys`. Без них push выключен, кабинет показывает «не настроено» |
| `NUM_PROXIES=1` | за reverse proxy: доверять `X-Forwarded-For`/`X-Forwarded-Proto` |
| `NEXT_PUBLIC_API_URL=https://api.<домен>` | frontend (задаётся при сборке образа) |

`DEV_FALLBACK` в production запрещён (бэкенд не стартует). Demo-режим включается сам, если ключей AI нет,
и всегда виден пользователю баннером.

## 2. Первый запуск

```bash
docker compose up -d --build        # сервис migrate сам применит миграции и сид, остальные ждут его
docker compose exec backend python manage.py createsuperuser        # роль admin
docker compose exec backend python manage.py admin_totp admin@example.com   # 2FA обязательна для админки
```

`admin_totp` печатает otpauth-URL и секрет для Google Authenticator / 1Password. Без устройства TOTP в
админку не войти ни в одном окружении. Потеря телефона — `admin_totp <email> --reset` с сервера.
Не запускайте команду там, где stdout попадает в логи.

Web Push: `docker compose run --rm backend python manage.py vapid_keys --subject mailto:ops@<домен>` печатает три
строки для `.env`; после их добавления перезапустите backend и worker. Смена приватного ключа обнуляет все
подписки устройств (родителям придётся включить push заново), поэтому ключ хранится как секрет и не ротируется без нужды.

## 3. Reverse proxy и заголовки

Пример Caddyfile:

```
app.example.kg {
    reverse_proxy frontend:3000
}
api.example.kg {
    reverse_proxy backend:8000
    request_body { max_size 60MB }   # до 5 фото по 10 МБ
}
```

Frontend сам отдаёт CSP с nonce (`frontend/src/proxy.ts`), HSTS, COOP, `X-Frame-Options: DENY`.
Backend включает HSTS (`SECURE_HSTS_SECONDS`, 30 дней по умолчанию; `SECURE_HSTS_PRELOAD=1` только после
года работы), `SECURE_SSL_REDIRECT`, secure-cookies. Refresh-токен живёт в HttpOnly-cookie с path
`/api/v1/auth/`; повторное использование уже ротированного токена отзывает все сессии пользователя.

## 4. Фоновые задачи (Celery beat)

| Задача | Расписание | Что делает |
|---|---|---|
| `purge_expired_images` | каждые 6 ч | удаляет фото заданий с истёкшим сроком хранения |
| `send_weekly_reports` | понедельник 09:00 | недельные отчёты родителям как уведомления в кабинете (не письма) |
| `check_ai_budget` | каждый час | письмо админам при расходе ≥ `AI_BUDGET_ALERT_THRESHOLD` (80 %) дневного бюджета |
| `send_push` | по событию, после коммита уведомления | Web Push на подписанные устройства родителя; мёртвые подписки (404/410) удаляются |

Сводка расходов для операторов: `GET /api/v1/admin/ai-usage/` (роль admin): сегодня/7 дней, по
назначению, провайдеру, модели, топ семей. Только агрегаты.

## 5. Резервные копии и обновления

- Postgres: `scripts/backup_db.sh` (pg_dump через compose, gzip, ретеншн `BACKUP_KEEP_DAYS`), в cron ежедневно;
  перед первым релизом и раз в квартал — тестовое восстановление (команда в шапке скрипта). Данные детей —
  персональные: каталог бэкапов на шифрованном томе, копии off-site тоже шифрованные.
- Хранилище фото: версионирование бакета или snapshot; фото и так удаляются по сроку.
- Обновление: `docker compose pull && docker compose up -d`, затем `migrate`. Миграции обратно совместимы
  в пределах одного релиза; destructive-миграций нет.
- Перед релизом: `cd backend && pytest && ruff check .`, `cd frontend && npm run typecheck && npm run lint && npm test && npm run build`,
  `/release-audit`.

## 6. Воспроизводимые зависимости

`backend/requirements.txt` задаёт диапазоны, `backend/requirements.lock.txt` — точные версии, с которыми
прогонялись тесты (снято с Windows-venv, содержит и dev-пакеты). Для образа можно ставить
`pip install -r requirements.lock.txt`; обновлять lock после `pip install -U` и зелёных тестов.

## 7. Что проверить после выкатки

1. `GET https://api.<домен>/api/v1/health/` → 200 с `database: true, cache: true` (503 при деградации),
   `GET /api/v1/meta/` → `demo_mode: false`, нужный `ai_provider`.
2. Регистрация родителя, вход ребёнка по коду семьи, фото задания → распознавание → объяснение.
3. Админка открывается только с кодом TOTP.
4. В логах нет `ai.budget_alert`; письмо-алерт приходит на `DJANGO_ADMINS` (можно проверить, временно снизив порог).
5. `curl -I https://app.<домен>/` содержит `content-security-policy` и `strict-transport-security`.
6. Кабинет родителя → Настройки → «Push на это устройство» включается (Chrome/Android; iOS — после установки на
   экран «Домой»), а `GET /api/v1/parents/push/` отдаёт `enabled: true`. Тестовое уведомление: несколько неверных
   PIN ребёнка подряд → push «Несколько неверных PIN подряд».
