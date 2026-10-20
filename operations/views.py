from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .backups import create_backup, validate_backup


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def backups(request):
    if not request.user.is_superuser:
        raise Http404
    directory = settings.DATA_DIR / "backups"
    error = None
    if request.method == "POST":
        try:
            create_backup(data_dir=settings.DATA_DIR, destination=directory)
            messages.success(request, "Backup created and verified.")
            return redirect("backups")
        except (OSError, ValueError, RuntimeError) as exc:
            error = str(exc)
    return render(
        request,
        "operations/backups.html",
        {
            "error": error,
            "backups": [p.name for p in sorted(directory.glob("register-*.zip"), reverse=True)],
        },
    )


@login_required
@never_cache
@require_http_methods(["GET"])
def download(request, filename):
    if (
        not request.user.is_superuser
        or not filename.startswith("register-")
        or not filename.endswith(".zip")
    ):
        raise Http404
    directory = (settings.DATA_DIR / "backups").resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        raise Http404
    validate_backup(path)
    return FileResponse(path.open("rb"), as_attachment=True, filename=filename)
