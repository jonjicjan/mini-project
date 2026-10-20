import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from exports.docx_render import render_booklet


class Command(BaseCommand):
    help = "Render the synthetic booklet print prototype (does not read register records)."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path, default=Path("artifacts/booklet-sample.docx"))
        parser.add_argument(
            "--fixture",
            type=Path,
            default=settings.BASE_DIR / "tests/fixtures/booklet_synthetic.json",
        )

    def handle(self, *args, **options):
        try:
            snapshot = json.loads(options["fixture"].read_text(encoding="utf-8"))
            warnings = render_booklet(snapshot, options["output"])
        except (ValueError, KeyError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        report = options["output"].with_suffix(".warnings.json")
        report.write_text(json.dumps(warnings, indent=2, ensure_ascii=False), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Created {options['output']}"))
        for warning in warnings:
            self.stderr.write(self.style.WARNING(warning))
        self.stdout.write(f"Fit warnings: {len(warnings)}. Report: {report}")
