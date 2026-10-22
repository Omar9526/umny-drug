"""Django admin requires a confirmed TOTP device and a valid code in addition to the password."""

from __future__ import annotations

import io

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

PASSWORD = "Strong-admin-pass-2026"
ADMIN_INDEX = f"/{settings.ADMIN_URL_PATH}"
ADMIN_LOGIN = f"{ADMIN_INDEX}login/"


@pytest.fixture(autouse=True)
def plain_static_storage(settings):
    # Admin templates use {% static %}; the manifest storage needs collectstatic, which tests skip.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_superuser("admin@example.com", PASSWORD)


def current_code(device: TOTPDevice) -> str:
    return f"{totp(device.bin_key, device.step, device.t0, device.digits, device.drift):0{device.digits}d}"


def test_otp_is_required_in_development():
    assert settings.ENVIRONMENT == "development"


def test_staff_without_device_cannot_log_in(client, staff_user):
    response = client.post(
        ADMIN_LOGIN,
        {"username": staff_user.email, "password": PASSWORD, "otp_token": "123456", "next": ADMIN_INDEX},
    )

    assert response.status_code == 200  # form re-rendered, no redirect to the index
    errors = response.context["form"].non_field_errors()
    assert any("не настроена двухфакторная аутентификация" in e for e in errors)
    assert client.get(ADMIN_INDEX).status_code == 302  # still redirected to login


def test_password_alone_is_not_enough(client, staff_user):
    TOTPDevice.objects.create(user=staff_user, name="phone", confirmed=True)

    response = client.post(ADMIN_LOGIN, {"username": staff_user.email, "password": PASSWORD})

    assert response.status_code == 200
    assert any("Введите шестизначный код" in e for e in response.context["form"].non_field_errors())
    assert client.get(ADMIN_INDEX).status_code == 302


def test_wrong_code_is_rejected(client, staff_user):
    device = TOTPDevice.objects.create(user=staff_user, name="phone", confirmed=True)
    wrong = f"{(int(current_code(device)) + 500_000) % 1_000_000:06d}"

    response = client.post(
        ADMIN_LOGIN, {"username": staff_user.email, "password": PASSWORD, "otp_token": wrong}
    )

    assert response.status_code == 200
    assert any("Неверный или устаревший код" in e for e in response.context["form"].non_field_errors())
    assert client.get(ADMIN_INDEX).status_code == 302


def test_staff_with_device_and_valid_code_logs_in(client, staff_user):
    device = TOTPDevice.objects.create(user=staff_user, name="phone", confirmed=True)

    response = client.post(
        ADMIN_LOGIN,
        {
            "username": staff_user.email,
            "password": PASSWORD,
            "otp_token": current_code(device),
            "next": ADMIN_INDEX,
        },
    )

    assert response.status_code == 302
    assert response["Location"] == ADMIN_INDEX
    index = client.get(ADMIN_INDEX)
    assert index.status_code == 200
    assert index.context["user"].is_verified()


def test_force_login_without_otp_has_no_admin_access(client, staff_user):
    client.force_login(staff_user)

    response = client.get(ADMIN_INDEX)

    assert response.status_code == 302
    assert response["Location"].startswith(ADMIN_LOGIN)


def test_admin_totp_command_creates_device(staff_user):
    out = io.StringIO()
    call_command("admin_totp", staff_user.email, stdout=out)

    device = TOTPDevice.objects.get(user=staff_user)
    assert device.confirmed
    output = out.getvalue()
    assert "otpauth://totp/" in output
    assert "Секрет (base32):" in output


def test_admin_totp_command_requires_reset_to_replace(staff_user):
    call_command("admin_totp", staff_user.email, stdout=io.StringIO())
    old_key = TOTPDevice.objects.get(user=staff_user).key

    with pytest.raises(CommandError):
        call_command("admin_totp", staff_user.email, stdout=io.StringIO())

    call_command("admin_totp", staff_user.email, "--reset", stdout=io.StringIO())
    devices = TOTPDevice.objects.filter(user=staff_user)
    assert devices.count() == 1
    assert devices.get().key != old_key


def test_admin_totp_command_rejects_non_staff(db):
    get_user_model().objects.create_user(
        "parent@example.com", PASSWORD, role="parent", display_name="Родитель"
    )

    with pytest.raises(CommandError):
        call_command("admin_totp", "parent@example.com", stdout=io.StringIO())


def test_admin_totp_command_lists_staff(staff_user):
    out = io.StringIO()
    call_command("admin_totp", stdout=out)

    assert f"{staff_user.email} [superuser]: нет TOTP-ключа" in out.getvalue()


def test_admin_totp_command_qr_without_package(staff_user):
    out = io.StringIO()
    call_command("admin_totp", staff_user.email, "--qr", stdout=out)

    assert "QR недоступен" in out.getvalue() or "█" in out.getvalue() or "#" in out.getvalue()
