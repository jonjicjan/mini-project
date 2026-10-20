import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.errors import DomainError

from .forms import ArchiveForm, RegisterForm
from .models import Register
from .services import create_register, owned_register, set_archived, update_register


@login_required
@never_cache
@require_GET
def register_list(request):
    owned = Register.objects.filter(owner=request.user)
    archived = request.GET.get("view") == "archived"
    registers = owned.filter(archived_at__isnull=not archived)
    query = request.GET.get("q", "").strip()
    if query:
        from django.db.models import Q

        registers = registers.filter(
            Q(subject_name__icontains=query)
            | Q(subject_code__icontains=query)
            | Q(branch__icontains=query)
            | Q(section__icontains=query)
        )
    return render(
        request,
        "registers/list.html",
        {
            "registers": registers,
            "archived": archived,
            "query": query,
            "active_count": owned.filter(archived_at__isnull=True).count(),
            "archived_count": owned.filter(archived_at__isnull=False).count(),
        },
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def setup(request, register_id=None):
    register = owned_register(request.user, register_id) if register_id else None
    revision = register.revision if register else request.user.revision
    initial = (
        {} if register else {"faculty_name": request.user.display_name or request.user.username}
    )
    form = RegisterForm(request.POST or None, instance=register, revision=revision, initial=initial)
    status = 200
    error_details = None
    if request.method == "POST":
        status = 422
        if form.is_valid():
            try:
                if register:
                    update_register(
                        request.user, register.pk, values=form.values(), **form.operation()
                    )
                    result_id = register.pk
                else:
                    result_id = create_register(
                        request.user, values=form.values(), **form.operation()
                    )["data"]["id"]
                messages.success(request, "Register saved.")
                return redirect("register-setup", register_id=result_id)
            except DomainError as error:
                form.show_domain_error(error)
                status = error.status
                error_details = error.body
    return render(
        request,
        "registers/setup.html",
        {
            "form": form,
            "register": register,
            "conflict": error_details if status == 409 else None,
        },
        status=status,
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def archive(request, register_id):
    register = owned_register(request.user, register_id)
    form = ArchiveForm(
        request.POST or None,
        revision=register.revision,
        initial={"archived": "no" if register.archived_at else "yes"},
    )
    status = 200
    if request.method == "POST":
        status = 422
        if form.is_valid():
            try:
                archived = form.cleaned_data["archived"]
                set_archived(request.user, register.pk, archived, **form.operation())
                messages.success(
                    request, "Register archived." if archived else "Register restored."
                )
                return redirect("register-list")
            except DomainError as error:
                form.show_domain_error(error)
                status = error.status
    return render(
        request, "registers/archive.html", {"register": register, "form": form}, status=status
    )


@login_required
@never_cache
@require_POST
def update_api(request, register_id):
    owned_register(request.user, register_id)
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict) or not isinstance(body.get("values"), dict):
            raise DomainError("Expected an object containing register values.")
        return JsonResponse(
            update_register(
                request.user,
                register_id,
                expected_revision=body.get("expected_revision"),
                request_id=body.get("request_id"),
                values=body["values"],
            )
        )
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"code": "invalid_json", "message": "Send valid JSON.", "field_errors": {}}, status=422
        )
    except DomainError as error:
        return JsonResponse(error.body, status=error.status)
