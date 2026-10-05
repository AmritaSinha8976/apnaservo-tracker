from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import DailyReport, WorkItem, Workday


class WorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("boss", "boss@x.com", "Adm1n-pass!", full_name="Boss")
        self.c = self.client

    def login(self, u, p):
        self.client.logout()
        return self.client.post(reverse("login"), {"username": u, "password": p}, follow=True)

    def test_full_flow(self):
        self.login("boss", "Adm1n-pass!")
        r = self.client.post(reverse("member_new"), {"full_name": "Amrita D", "email": "a@x.com", "username": "amrita",
                             "role": "MEMBER", "password": "Temp-pass-1", "phone": "", "designation": ""})
        self.assertContains(r, "Temp-pass-1")
        am = User.objects.get(username="amrita")
        self.assertNotEqual(am.password, "Temp-pass-1")  # hashed
        self.client.post(reverse("tasks"), {"title": "Fix login API", "priority": "HIGH", "assigned_to": am.pk})
        self.client.post(reverse("tasks"), {"title": "Unassigned thing", "priority": "LOW", "assigned_to": ""})
        self.assertEqual(WorkItem.objects.filter(assigned_to__isnull=True).count(), 1)
        # member: forced password change
        r = self.login("amrita", "Temp-pass-1")
        self.assertContains(r, "Set your new password")
        self.assertRedirects(self.client.get("/"), reverse("password_change"))
        r = self.client.post(reverse("password_change"), {"old_password": "Temp-pass-1", "new_password1": "Temp-pass-1", "new_password2": "Temp-pass-1"})
        self.assertContains(r, "different from your current")
        r = self.client.post(reverse("password_change"), {"old_password": "Temp-pass-1", "new_password1": "Brand-new-77x", "new_password2": "Brand-new-77x"}, follow=True)
        self.assertContains(r, "Fix login API")
        self.assertNotContains(r, "Unassigned thing")
        # member can't see admin pages
        self.assertEqual(self.client.get("/admin-panel/").status_code, 403)
        # work, status, note
        self.client.post(reverse("work_add"), {"title": "Social media designs"})
        t = WorkItem.objects.get(title="Fix login API")
        self.client.post(reverse("item_status", args=[t.pk]), {"status": "COMPLETED"})
        self.client.post(reverse("note_add"), {"kind": "BLOCKER", "body": "Waiting on API keys"})
        # logout is blocked until the report is done
        self.assertRedirects(self.client.post(reverse("logout")), reverse("end_day"))
        r = self.client.post(reverse("end_day"), {"todays_work": ""})
        self.assertContains(r, "This field is required")
        r = self.client.post(reverse("end_day"), {"todays_work": "- Fixed login\n- Designs", "blockers": "API keys"}, follow=True)
        self.assertContains(r, "daily report has been saved")
        rep = DailyReport.objects.get()
        self.assertEqual(rep.work_lines, ["Fixed login", "Designs"])
        self.assertEqual(rep.workday.state, Workday.ENDED)
        self.assertEqual(len(rep.snapshot["assigned"]), 1)
        self.assertEqual(len(rep.snapshot["self"]), 1)
        # other member can't read it; admin can
        User.objects.create_user("raj", "r@x.com", "Pass-word-9x", full_name="Raj", must_change_password=False)
        self.login("raj", "Pass-word-9x")
        self.assertEqual(self.client.get(reverse("report_detail", args=[rep.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("item_status", args=[t.pk]), {"status": "PENDING"}).status_code, 404)
        self.login("boss", "Adm1n-pass!")
        r = self.client.get(reverse("report_detail", args=[rep.pk]))
        self.assertContains(r, "Fixed login")
        r = self.client.get(reverse("admin_dashboard"))
        self.assertContains(r, "Amrita D"); self.assertContains(r, "Haven't submitted")
        r = self.client.get(reverse("reports") + f"?date={timezone.localdate():%Y-%m-%d}")
        self.assertContains(r, "Fixed login"); self.assertContains(r, "Raj")
        self.assertEqual(self.client.get(reverse("member_detail", args=[am.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("members") + "?q=amr").status_code, 200)
        self.assertEqual(self.client.get(reverse("tasks") + "?member=none&status=PENDING").status_code, 200)
        r = self.client.post(reverse("member_reset_password", args=[am.pk]))
        self.assertContains(r, "shown only once"); am.refresh_from_db(); self.assertTrue(am.must_change_password)

    def test_anonymous_redirected(self):
        for url in ("/", "/admin-panel/", "/my/end-day/"):
            self.assertEqual(self.client.get(url).status_code, 302)
