"""Create (or reset) a confirmed TOTP device for a staff user so they can log in to Django admin."""

from __future__ import annotations

import io
from base64 import b32encode

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_otp.plugins.otp_totp.models import TOTPDevice

DEVICE_NAME = "admin-totp"


class Command(BaseCommand):
    help = (
        "Создаёт подтверждённый TOTP-ключ для staff-пользователя и печатает otpauth:// URL и секрет. "
        "Без email — список staff-пользователей и их устройств."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", nargs="?", help="Email staff-пользователя")
        parser.add_argument(
            "--reset", action="store_true", help="Удалить существующие TOTP-ключи и создать новый"
        )
        parser.add_argument("--qr", action="store_true", help="Напечатать ASCII-QR (нужен пакет qrcode)")

    def handle(self, *args, email=None, reset=False, qr=False, **options):
        if not email:
            self._list_staff()
            return

        user = get_user_model().objects.filter(email__iexact=email.strip()).first()
        if user is None:
            raise CommandError(f"Пользователь {email} не найден.")
        if not user.is_staff:
            raise CommandError(f"Пользователь {email} не staff: вход в админку ему недоступен.")

        with transaction.atomic():
            existing = TOTPDevice.objects.select_for_update().filter(user=user)
            if existing.exists():
                if not reset:
                    raise CommandError(
                        f"У {email} уже есть TOTP-ключ. Чтобы выпустить новый (старый перестанет работать), "
                        "добавьте --reset."
                    )
                existing.delete()
            device = TOTPDevice.objects.create(user=user, name=DEVICE_NAME, confirmed=True)

        secret = b32encode(device.bin_key).decode()
        self.stdout.write(self.style.SUCCESS(f"TOTP-ключ для {user.email} создан."))
        self.stdout.write(f"otpauth URL: {device.config_url}")
        self.stdout.write(f"Секрет (base32): {secret}")
        self.stdout.write("Добавьте ключ в Google Authenticator / 1Password и никому его не передавайте.")
        if qr:
            self._print_qr(device.config_url)

    def _list_staff(self):
        users = get_user_model().objects.filter(is_staff=True).order_by("email")
        if not users:
            self.stdout.write("Staff-пользователей нет.")
            return
        devices: dict = {}
        for device in TOTPDevice.objects.filter(user__in=users):
            devices.setdefault(device.user_id, []).append(device)
        for user in users:
            user_devices = devices.get(user.pk, [])
            if user_devices:
                described = ", ".join(
                    f"{d.name} ({'подтверждён' if d.confirmed else 'не подтверждён'})" for d in user_devices
                )
            else:
                described = "нет TOTP-ключа"
            superuser = " [superuser]" if user.is_superuser else ""
            self.stdout.write(f"{user.email}{superuser}: {described}")

    def _print_qr(self, url: str):
        try:
            import qrcode
        except ImportError:
            self.stdout.write("QR недоступен: пакет qrcode не установлен (pip install qrcode).")
            return
        code = qrcode.QRCode(border=1)
        code.add_data(url)
        buffer = io.StringIO()
        code.print_ascii(out=buffer, invert=True)
        self.stdout.write(buffer.getvalue())
