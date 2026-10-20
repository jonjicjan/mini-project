from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from .middleware import save_session_version

        user_logged_in.connect(save_session_version, dispatch_uid="register.session-version")
