import secrets
from django import forms
from django.contrib.auth import get_user_model
from .models import DailyReport, Note, TaskComment, WorkItem

User = get_user_model()


def new_password():
    return secrets.token_urlsafe(7)


class WorkForm(forms.ModelForm):
    class Meta:
        model = WorkItem
        fields = ["title", "description", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "What are you working on today?"}),
            "description": forms.Textarea(attrs={"rows": 2, "placeholder": "Details (optional)"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"due_date": "Deadline (optional)", "description": "Details (optional)"}


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["kind", "body"]
        labels = {"kind": "Type", "body": "Note"}
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Updates, problems, things to remember…"})}


class ReportForm(forms.ModelForm):
    class Meta:
        model = DailyReport
        fields = ["todays_work", "pending_work", "blockers", "notes"]
        labels = {"todays_work": "Today's Work", "pending_work": "Pending Work (optional)",
                  "blockers": "Blockers (optional)", "notes": "Notes for the team (optional)"}
        widgets = {
            "todays_work": forms.Textarea(attrs={"rows": 6, "placeholder": "One item per line:\n- Fixed login issue\n- Created 3 social media designs"}),
            "pending_work": forms.Textarea(attrs={"rows": 3, "placeholder": "What is still incomplete?"}),
            "blockers": forms.Textarea(attrs={"rows": 3, "placeholder": "What stopped you from finishing something?"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_todays_work(self):
        v = self.cleaned_data["todays_work"].strip()
        if not v:
            raise forms.ValidationError("Please list what you worked on today.")
        return v


class MemberForm(forms.ModelForm):
    password = forms.CharField(label="Initial password", min_length=8,
                               help_text="Share this with the member. They must change it on first login.")

    class Meta:
        model = User
        fields = ["full_name", "email", "phone", "username", "designation", "role"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["password"].initial = new_password()
        self.fields["email"].required = True

    def clean_email(self):
        e = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("A member with this email already exists.")
        return e

    def save(self, commit=True):
        u = super().save(commit=False)
        u.set_password(self.cleaned_data["password"])
        u.must_change_password = True
        u.save()
        return u


class TaskEditForm(forms.ModelForm):
    class Meta:
        model = WorkItem
        fields = ["title", "description", "assigned_to", "priority", "due_date"]
        labels = {"assigned_to": "Assign to (optional)"}
        widgets = {"description": forms.Textarea(attrs={"rows": 2}), "due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["assigned_to"].queryset = User.objects.filter(role="MEMBER", is_active=True).order_by("full_name")
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].empty_label = "— Unassigned —"


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ["body"]
        labels = {"body": ""}
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Add an update or comment…"})}
