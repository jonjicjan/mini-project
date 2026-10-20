from django.contrib.auth import logout


def save_session_version(sender, request, user, **kwargs):
    request.session["account_version"] = user.session_version


class SessionVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and (
            request.session.get("account_version") != request.user.session_version
        ):
            logout(request)
        return self.get_response(request)
