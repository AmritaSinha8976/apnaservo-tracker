from django.shortcuts import redirect


class ForcePasswordChangeMiddleware:
    """Members with a temporary password can only reach the change-password page."""
    EXEMPT = ("/password/change/", "/logout/", "/static/", "/django-admin/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = request.user
        if u.is_authenticated and u.must_change_password and not request.path.startswith(self.EXEMPT):
            return redirect("password_change")
        return self.get_response(request)
