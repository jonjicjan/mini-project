from django.urls import include, path

from operations import views as operations_views

urlpatterns = [path("", include("accounts.urls")), path("", include("registers.urls"))]
urlpatterns += [
    path("admin/backups/", operations_views.backups, name="backups"),
    path("admin/backups/<str:filename>/", operations_views.download, name="backup-download"),
]
