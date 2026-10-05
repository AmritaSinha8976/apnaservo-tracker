from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


@override_settings(AUTH_PASSWORD_VALIDATORS=[])
class BootstrapAdminCommandTests(TestCase):
    def test_skips_when_no_bootstrap_values_are_configured(self):
        output = StringIO()
        with patch.dict("os.environ", {}, clear=True):
            call_command("bootstrap_admin", stdout=output)

        self.assertIn("skipped", output.getvalue())

    def test_creates_initial_admin_from_environment(self):
        env = {
            "BOOTSTRAP_ADMIN_USERNAME": "firstadmin",
            "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "BOOTSTRAP_ADMIN_FULL_NAME": "First Admin",
            "BOOTSTRAP_ADMIN_PASSWORD": "a-long-test-password",
        }
        with patch.dict("os.environ", env):
            call_command("bootstrap_admin")

        admin = get_user_model().objects.get(username="firstadmin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_admin_role)
        self.assertTrue(admin.check_password("a-long-test-password"))

    def test_requires_all_values_when_bootstrapping(self):
        env = {
            "BOOTSTRAP_ADMIN_USERNAME": "firstadmin",
            "BOOTSTRAP_ADMIN_EMAIL": "",
            "BOOTSTRAP_ADMIN_FULL_NAME": "First Admin",
            "BOOTSTRAP_ADMIN_PASSWORD": "a-long-test-password",
        }
        with patch.dict("os.environ", env):
            with self.assertRaises(CommandError):
                call_command("bootstrap_admin")

    def test_does_not_change_existing_admin(self):
        User = get_user_model()
        User.objects.create_superuser(
            username="firstadmin",
            email="admin@example.com",
            password="original-test-password",
            full_name="First Admin",
        )
        env = {
            "BOOTSTRAP_ADMIN_USERNAME": "firstadmin",
            "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "BOOTSTRAP_ADMIN_FULL_NAME": "First Admin",
            "BOOTSTRAP_ADMIN_PASSWORD": "another-test-password",
        }
        with patch.dict("os.environ", env):
            call_command("bootstrap_admin")

        admin = User.objects.get(username="firstadmin")
        self.assertTrue(admin.check_password("original-test-password"))
