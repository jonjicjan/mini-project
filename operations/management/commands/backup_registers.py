from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from operations.backups import create_backup


class Command(BaseCommand):
    help = "Create a verified online backup of accounts, registers and issued documents."

    def add_arguments(self, parser):
        parser.add_argument("--destination", type=Path)

    def handle(self, *args, **options):
        try:
            path = create_backup(
                data_dir=settings.DATA_DIR,
                destination=options["destination"] or settings.DATA_DIR / "backups",
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(str(path))
