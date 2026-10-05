from django import forms
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import User


class Login(LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or ("/admin-panel/" if self.request.user.is_admin_role else "/")


@require_POST
def logout_view(request):
    from tracker.models import Workday
    u = request.user
    if u.is_authenticated and not u.is_admin_role and not u.must_change_password:
        wd = Workday.objects.filter(user=u, date=timezone.localdate()).first()
        if wd and wd.state == Workday.ACTIVE:
            messages.info(request, "Please complete today's report to end your day.")
            return redirect("end_day")
    logout(request)
    return redirect("login")


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["old_password"] == form.cleaned_data["new_password1"]:
            form.add_error("new_password1", "Please choose a password different from your current one.")
        else:
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been updated.")
            return redirect("home")
    return render(request, "password_change.html", {"form": form, "forced": request.user.must_change_password})


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["phone"]


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "profile.html", {"form": form})
