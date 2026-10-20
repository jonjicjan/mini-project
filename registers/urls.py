from django.urls import path

from . import views, workviews

urlpatterns = [
    path(
        "registers/<uuid:register_id>/work/<str:tab>/",
        workviews.workspace,
        name="register-workspace",
    ),
    path("exports/<uuid:export_id>/download/", workviews.download_export, name="export-download"),
    path("exports/<uuid:export_id>/preview/", workviews.export_preview, name="export-preview"),
    path("", views.register_list, name="register-list"),
    path("registers/new/", views.setup, name="register-create"),
    path("registers/<uuid:register_id>/", views.setup, name="register-setup"),
    path("registers/<uuid:register_id>/archive/", views.archive, name="register-archive"),
    path("api/registers/<uuid:register_id>/", views.update_api, name="register-update-api"),
]
