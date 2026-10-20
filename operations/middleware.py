from django.conf import settings
from django.http import HttpResponse


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (settings.DATA_DIR / "maintenance.flag").exists():
            return HttpResponse("Maintenance is in progress. Please retry shortly.", status=503)
        return self.get_response(request)
