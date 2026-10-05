from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.Login.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password/change/", views.password_change, name="password_change"),
    path("profile/", views.profile, name="profile"),
]
