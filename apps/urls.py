from django.urls import path

from apps.views import (
    ActivateEmailView,
    DashboardView,
    ForbiddenView,
    UserLoginView,
    PasswordResetView,
    ProfileView,
    RegisterView,
    SessionsView,
    VerifyEmailView, UserLogout,
)

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogout.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("password-reset/", PasswordResetView.as_view(), name="password_reset"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path(
        "verify-email/<uidb64>/<token>/",
        ActivateEmailView.as_view(),
        name="activate_email",
    ),
    path("", DashboardView.as_view(), name="dashboard"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("sessions/", SessionsView.as_view(), name="sessions"),
    path("forbidden/", ForbiddenView.as_view(), name="forbidden"),
]
