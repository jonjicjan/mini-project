"""Create the initial administrator interactively without a default password."""

import getpass
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.services import validate_user
from core.errors import DomainError
from core.models import AuditEvent
from core.mutations import json_value


class Command(BaseCommand):
    help = "Create the first administrator using interactive prompts. Never accepts a password argument."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-missing",
            action="store_true",
            help="Do nothing when an administrator already exists.",
        )

    def handle(self, *args, **options):
        model = get_user_model()
        if model.objects.filter(is_superuser=True).exists():
            if options["if_missing"]:
                return
            raise CommandError("An administrator already exists. Use changepassword for recovery.")
        username = input("Administrator username: ").strip().lower()
        display_name = input("Administrator display name: ").strip()
        password = getpass.getpass("Password (at least 12 characters): ")
        if password != getpass.getpass("Confirm password: "):
            raise CommandError("Passwords do not match.")
        user = model(username=username, display_name=display_name, is_staff=True, is_superuser=True)
        try:
            validate_user(user, password)
        except DomainError as error:
            raise CommandError(str(error.body["field_errors"])) from error
        user.set_password(password)
        with transaction.atomic():
            if model.objects.filter(is_superuser=True).exists():
                raise CommandError("Another administrator was created. No account was added.")
            user.save()
            AuditEvent.objects.create(
                actor=user,
                scope=f"accounts.user:{user.pk}",
                action="bootstrap_admin",
                before={},
                after=json_value(user.audit_state()),
                request_id=uuid.uuid4(),
            )
        self.stdout.write(self.style.SUCCESS("Administrator created. You can now sign in."))
