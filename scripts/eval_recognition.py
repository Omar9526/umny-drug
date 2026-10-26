# ruff: noqa: T201 — консольный скрипт, печать и есть результат
"""Прогон распознавания на реальных фото тетрадей через API «Умного друга».

Положите фото (jpg/jpeg/png/webp/heic) в папку. Рядом с фото можно положить файл ``<имя>.expected.txt``
с эталонным текстом: одно задание — один абзац, задания разделяются пустой строкой. Скрипт входит как
ребёнок, загружает каждое фото через ``POST /api/v1/assignments/upload/``, дожидается результата и печатает
таблицу (статус, число заданий, предмет, похожесть на эталон, время), а подробности пишет в JSON.

Нужен запущенный backend с реальным провайдером (Gemini или Anthropic): в demo-режиме распознавание
скриптовое и для оценки качества бессмысленно — скрипт это заметит и предупредит. Каждое фото — реальный
вызов модели (расход бюджета). Лимит загрузок ``THROTTLE_UPLOAD`` по умолчанию 20/час; для большого прогона
временно ослабьте его в ``.env`` или задайте ``--sleep``.

Пример (демо-семья с машины разработки):

    set UD_CHILD_PIN=2468
    backend/.venv/Scripts/python.exe scripts/eval_recognition.py --photos ~/Pictures/tetradi \\
        --family-code 67J-8X7 --child Алина --out recognition-report.json
"""

from __future__ import annotations

import argparse
import difflib
import getpass
import json
import mimetypes
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
PENDING_STATUSES = {"pending", "processing"}
POLL_INTERVAL_S = 2.0
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/heif", ".heif")


@dataclass
class PhotoResult:
    photo: str
    status: str
    seconds: float
    tasks: list[dict] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)
    similarity: float | None = None
    matched: int = 0
    demo_mode: bool = False
    error: str | None = None
    upload_id: str | None = None


def normalize(text: str) -> str:
    text = text.replace("$", " ").lower()
    text = re.sub(r"[^\w\s+\-=*/^()<>.,:;?!%°]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(expected: str, recognized: str) -> float:
    return difflib.SequenceMatcher(None, normalize(expected), normalize(recognized)).ratio()


def expected_tasks_for(photo: Path) -> list[str]:
    sidecar = photo.with_suffix(photo.suffix + ".expected.txt")
    if not sidecar.exists():
        sidecar = photo.with_suffix(".expected.txt")
    if not sidecar.exists():
        return []
    chunks = re.split(r"\n\s*\n", sidecar.read_text(encoding="utf-8").strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def score(expected: list[str], tasks: list[dict], threshold: float) -> tuple[float | None, int]:
    """Average best-match similarity per expected task and how many cleared the threshold."""
    if not expected:
        return None, 0
    recognized = [task.get("text", "") for task in tasks]
    best = [max((similarity(exp, rec) for rec in recognized), default=0.0) for exp in expected]
    return sum(best) / len(best), sum(1 for value in best if value >= threshold)


def api_error(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
        return f"{response.status_code} {error.get('code', '')}: {error.get('message', '')}".strip()
    except ValueError:
        return f"{response.status_code} {response.text[:200]}"


def login_as_child(client: httpx.Client, family_code: str, pin: str, nickname: str | None) -> str:
    lookup = client.post("/api/v1/auth/child/lookup/", json={"family_code": family_code})
    if lookup.status_code != 200:
        sys.exit(f"Код семьи не принят: {api_error(lookup)}")
    children = lookup.json()["children"]
    if nickname:
        children = [child for child in children if child["nickname"].casefold() == nickname.casefold()]
    if len(children) != 1:
        names = ", ".join(child["nickname"] for child in lookup.json()["children"]) or "нет активных детей"
        sys.exit(f"Укажите ребёнка через --child (доступны: {names}).")
    login = client.post(
        "/api/v1/auth/child/login/",
        json={"family_code": family_code, "student_id": children[0]["id"], "pin": pin},
    )
    if login.status_code != 200:
        sys.exit(f"Вход ребёнка не удался: {api_error(login)}")
    return login.json()["access"]


def wait_for_result(client: httpx.Client, upload: dict, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    while upload["status"] in PENDING_STATUSES and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        response = client.get(f"/api/v1/assignments/uploads/{upload['id']}/")
        response.raise_for_status()
        upload = response.json()
    return upload


def run_photo(client: httpx.Client, photo: Path, args: argparse.Namespace) -> PhotoResult:
    started = time.monotonic()
    expected = expected_tasks_for(photo)
    mime = mimetypes.guess_type(photo.name)[0] or "application/octet-stream"
    data = {"source": "gallery"}
    if args.language:
        data["language_hint"] = args.language
    with photo.open("rb") as handle:
        response = client.post(
            "/api/v1/assignments/upload/",
            data=data,
            files=[("images", (photo.name, handle, mime))],
            timeout=args.timeout + 30,
        )
    if response.status_code != 201:
        return PhotoResult(
            photo=photo.name,
            status="http_error",
            seconds=time.monotonic() - started,
            expected=expected,
            error=api_error(response),
        )
    upload = wait_for_result(client, response.json(), args.timeout)
    tasks = [
        {
            "label": task.get("label", ""),
            "text": task.get("text", ""),
            "subject": (task.get("subject") or {}).get("slug"),
            "topic": (task.get("topic") or {}).get("name"),
        }
        for task in upload.get("tasks", [])
    ]
    avg, matched = score(expected, tasks, args.threshold)
    error = upload.get("error_message") or None
    if upload["status"] in PENDING_STATUSES:
        error = f"нет результата за {args.timeout:.0f} с"
    return PhotoResult(
        photo=photo.name,
        status=upload["status"],
        seconds=time.monotonic() - started,
        tasks=tasks,
        expected=expected,
        similarity=avg,
        matched=matched,
        demo_mode=bool(upload.get("demo_mode")),
        error=error,
        upload_id=upload.get("id"),
    )


def print_table(results: list[PhotoResult], threshold: float) -> None:
    width = max((len(result.photo) for result in results), default=10)
    header = (
        f"{'фото':<{width}}  {'статус':<12} {'задач':>5} {'предмет':<12} "
        f"{'похожесть':>9} {'эталон':>7} {'сек':>6}"
    )
    print(header)
    print("-" * len(header))
    for result in results:
        subject = next((task["subject"] for task in result.tasks if task["subject"]), "") or ""
        sim = f"{result.similarity:.2f}" if result.similarity is not None else "—"
        matched = f"{result.matched}/{len(result.expected)}" if result.expected else "—"
        print(
            f"{result.photo:<{width}}  {result.status:<12} {len(result.tasks):>5} {subject:<12} {sim:>9} "
            f"{matched:>7} {result.seconds:>6.1f}"
        )
        if result.error:
            print(f"{'':<{width}}  ! {result.error}")
    scored = [result for result in results if result.similarity is not None]
    recognized = sum(1 for result in results if result.status == "recognized")
    print("-" * len(header))
    print(f"распознано: {recognized}/{len(results)}")
    if scored:
        avg = sum(result.similarity for result in scored if result.similarity is not None) / len(scored)
        matched = sum(result.matched for result in scored)
        total = sum(len(result.expected) for result in scored)
        print(f"средняя похожесть на эталон: {avg:.2f}; заданий ≥ {threshold:.2f}: {matched}/{total}")
    if any(result.demo_mode for result in results):
        print("ВНИМАНИЕ: backend работает в demo-режиме — это не оценка реальной модели.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--photos", required=True, type=Path, help="папка с фото (или одно фото)")
    parser.add_argument("--family-code", required=True, help="код семьи из кабинета родителя, напр. 67J-8X7")
    parser.add_argument("--pin", help="PIN ребёнка; лучше переменная UD_CHILD_PIN или скрытый ввод без флага")
    parser.add_argument("--child", help="никнейм ребёнка, если в семье их несколько")
    parser.add_argument("--api", default="http://localhost:8000", help="адрес backend")
    parser.add_argument("--language", choices=("ru", "ky"), help="подсказка языка задания")
    parser.add_argument("--timeout", type=float, default=90.0, help="сколько ждать результат одного фото, с")
    parser.add_argument("--threshold", type=float, default=0.8, help="похожесть, при которой задание узнано")
    parser.add_argument("--sleep", type=float, default=0.0, help="пауза между фото, с (лимит загрузок)")
    parser.add_argument("--out", type=Path, help="куда записать JSON-отчёт с полными текстами")
    args = parser.parse_args()
    host = urlsplit(args.api).hostname or ""
    if args.api.startswith("http://") and host not in ("localhost", "127.0.0.1"):
        sys.exit("Для удалённого backend нужен https://: PIN и токен не должны идти открытым текстом.")
    pin = args.pin or os.environ.get("UD_CHILD_PIN") or getpass.getpass("PIN ребёнка: ")

    photos = (
        [args.photos]
        if args.photos.is_file()
        else sorted(path for path in args.photos.iterdir() if path.suffix.lower() in PHOTO_SUFFIXES)
    )
    if not photos:
        sys.exit(f"В {args.photos} нет фото ({', '.join(sorted(PHOTO_SUFFIXES))}).")

    with httpx.Client(base_url=args.api.rstrip("/"), timeout=30.0) as client:
        access = login_as_child(client, args.family_code, pin, args.child)
        client.headers["Authorization"] = f"Bearer {access}"
        results: list[PhotoResult] = []
        for index, photo in enumerate(photos, start=1):
            print(f"[{index}/{len(photos)}] {photo.name} …", end=" ", flush=True)
            result = run_photo(client, photo, args)
            print(f"{result.status} ({result.seconds:.1f} с)")
            results.append(result)
            if args.sleep and index < len(photos):
                time.sleep(args.sleep)

    print()
    print_table(results, args.threshold)
    if args.out:
        report = json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2)
        args.out.write_text(report, "utf-8")
        print(f"JSON-отчёт: {args.out}")
    return 0 if all(result.status == "recognized" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
