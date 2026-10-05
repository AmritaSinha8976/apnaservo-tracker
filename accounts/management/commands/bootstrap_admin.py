import os

from django.contrib.auth import get_user_model, password_validation
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial admin from temporary environment variables, if configured."

    def handle(self, *args, **options):
        names = (
            "BOOTSTRAP_ADMIN_USERNAME",
            "BOOTSTRAP_ADMIN_EMAIL",
            "BOOTSTRAP_ADMIN_FULL_NAME",
            "BOOTSTRAP_ADMIN_PASSWORD",
        )
        values = {name: os.environ.get(name, "") for name in names}
        if not any(values.values()):
            self.stdout.write("Initial admin setup skipped; no bootstrap credentials configured.")
            return

        missing = [name for name, value in values.items() if not value]
        if missing:
            raise CommandError(f"Missing required environment variables: {', '.join(missing)}")

        User = get_user_model()
        username = values["BOOTSTRAP_ADMIN_USERNAME"]
        existing = User.objects.filter(username=username).first()
        if existing:
            if not existing.is_superuser:
                raise CommandError(f"Username {username!r} already exists and is not an admin.")
            self.stdout.write(f"Admin {username!r} already exists; no changes made.")
            return

        user = User(
            username=username,
            email=values["BOOTSTRAP_ADMIN_EMAIL"],
            full_name=values["BOOTSTRAP_ADMIN_FULL_NAME"],
        )
        password = values["BOOTSTRAP_ADMIN_PASSWORD"]
        password_validation.validate_password(password, user)
        User.objects.create_superuser(
            username=username,
            email=user.email,
            password=password,
            full_name=user.full_name,
        )
        self.stdout.write(self.style.SUCCESS(f"Created initial admin {username!r}."))
