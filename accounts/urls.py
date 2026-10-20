from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.sign_in, name="login"),
    path("logout/", views.sign_out, name="logout"),
    path("health/", views.health, name="health"),
    path("admin/faculty/", views.manage_faculty, name="faculty-manage"),
    path(
        "admin/faculty/<int:user_id>/reset/",
        views.manage_account,
        {"action": "reset"},
        name="faculty-reset",
    ),
    path(
        "admin/faculty/<int:user_id>/disable/",
        views.manage_account,
        {"action": "disable"},
        name="faculty-disable",
    ),
    path(
        "admin/faculty/<int:user_id>/enable/",
        views.manage_account,
        {"action": "enable"},
        name="faculty-enable",
    ),
]
