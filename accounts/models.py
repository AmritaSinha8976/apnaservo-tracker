from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ADMIN, MEMBER = "ADMIN", "MEMBER"
    ROLES = [(ADMIN, "Admin"), (MEMBER, "Member")]

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=10, choices=ROLES, default=MEMBER)
    must_change_password = models.BooleanField(default=True)
    REQUIRED_FIELDS = ["email", "full_name"]

    @property
    def is_admin_role(self):
        return self.role == self.ADMIN

    def save(self, *args, **kwargs):
        if self._state.adding and self.is_superuser:
            self.role = self.ADMIN
            self.must_change_password = False
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.username
