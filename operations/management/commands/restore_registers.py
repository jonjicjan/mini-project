from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from operations.backups import restore_backup


class Command(BaseCommand):
    help = "Restore offline after stopping the application; creates a recovery backup."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("archive", type=Path)
        parser.add_argument("--maintenance", action="store_true")

    def handle(self, *args, **options):
        connections.close_all()
        try:
            result = restore_backup(
                archive=options["archive"],
                data_dir=settings.DATA_DIR,
                maintenance=options["maintenance"],
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(str(result))
