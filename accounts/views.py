from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.errors import DomainError
from core.forms import MutationForm

from .forms import FacultyForm, LoginForm, ResetForm
from .services import create_faculty, require_admin, reset_faculty_password, set_faculty_active
from .throttle import attempt_login


@never_cache
@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("register-list")
    form = LoginForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        user, blocked = attempt_login(request, **form.cleaned_data)
        if blocked:
            form.add_error(None, "Too many login attempts. Please try again in 15 minutes.")
            status = 429
        elif user:
            login(request, user)
            target = request.GET.get("next", "/")
            if not url_has_allowed_host_and_scheme(
                target, {request.get_host()}, require_https=request.is_secure()
            ):
                target = "/"
            return redirect(target)
        else:
            form.add_error(
                None, "The username or password is incorrect, or this account is disabled."
            )
    return render(request, "accounts/login.html", {"form": form}, status=status)


@require_POST
def sign_out(request):
    logout(request)
    return redirect("login")


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@login_required
@never_cache
@sensitive_post_parameters("temporary_password")
@require_http_methods(["GET", "POST"])
def manage_faculty(request):
    require_admin(request.user)
    form = FacultyForm(request.POST or None, revision=request.user.revision)
    status = 200
    if request.method == "POST":
        status = 422
        if form.is_valid():
            try:
                create_faculty(request.user, **form.cleaned_data)
                messages.success(request, "Faculty account created.")
                return redirect("faculty-manage")
            except DomainError as error:
                form.show_domain_error(error)
                status = error.status
    users = get_user_model().objects.filter(is_superuser=False).order_by("username")
    return render(
        request, "accounts/manage.html", {"form": form, "faculty_users": users}, status=status
    )


@login_required
@never_cache
@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def manage_account(request, user_id, action):
    require_admin(request.user)
    user = get_object_or_404(get_user_model(), pk=user_id, is_superuser=False)
    form_class = ResetForm if action == "reset" else MutationForm
    form = form_class(request.POST or None, revision=user.revision)
    status = 200
    if request.method == "POST":
        status = 422
        if form.is_valid():
            try:
                if action == "reset":
                    reset_faculty_password(request.user, user.pk, **form.cleaned_data)
                else:
                    set_faculty_active(
                        request.user, user.pk, action == "enable", **form.operation()
                    )
                messages.success(
                    request, "Account updated. Previous sessions have been invalidated."
                )
                return redirect("faculty-manage")
            except DomainError as error:
                form.show_domain_error(error)
                status = error.status
    return render(
        request,
        "accounts/action.html",
        {"form": form, "account": user, "action": action},
        status=status,
    )
