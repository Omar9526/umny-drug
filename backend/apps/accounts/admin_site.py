"""Django admin that requires a second factor (TOTP via django-otp) in every environment."""

from __future__ import annotations

from django import forms
from django_otp import devices_for_user
from django_otp.admin import OTPAdminAuthenticationForm, OTPAdminSite

NO_DEVICE_MESSAGE = (
    "Для этой учётной записи не настроена двухфакторная аутентификация. "
    "Администратор сервера должен выполнить «manage.py admin_totp <email>» и добавить ключ "
    "в приложение-аутентификатор."
)


class AdminOTPLoginForm(OTPAdminAuthenticationForm):
    """Admin login form: password + TOTP code, with Russian messages."""

    otp_error_messages = dict(
        OTPAdminAuthenticationForm.otp_error_messages,
        token_required="Введите шестизначный код из приложения-аутентификатора.",
        invalid_token="Неверный или устаревший код подтверждения. Попробуйте ещё раз.",
        device_required="Выберите устройство двухфакторной аутентификации.",
        verification_not_allowed="Проверка кода временно отключена. Повторите попытку позже.",
    )

    def clean_otp(self, user):
        # The password is already verified at this point, so telling the user that 2FA is not set
        # up does not leak anything to someone who does not know the password.
        if user is not None and not any(devices_for_user(user)):
            raise forms.ValidationError(NO_DEVICE_MESSAGE, code="otp_not_configured")
        super().clean_otp(user)

    def _chosen_device(self, user):
        device = super()._chosen_device(user)
        if device is None:
            # Most admins have exactly one authenticator; pick it instead of asking to choose.
            devices = list(devices_for_user(user, for_verify=True))
            if len(devices) == 1:
                device = devices[0]
        return device


class AdminOTPSite(OTPAdminSite):
    login_form = AdminOTPLoginForm
