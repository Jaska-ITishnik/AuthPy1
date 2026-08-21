from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.emails import send_verification_email
from apps.forms import RegistrationForm, LoginForm
from apps.models import User
from apps.tokens import email_verification_token


class UserLoginView(FormView):
    template_name = "login.html"
    form_class = LoginForm

    # def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
    #     email = request.POST.get("email")
    #     password = request.POST.get("password")
    #     user = authenticate(request, email=email, password=password)
    #     if not user:
    #         raise ValidationError("Bunday foydalanuvchi mavjud emas!")
    #     login(request, user, )

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return redirect('dashboard')

    def form_invalid(self, form) -> HttpResponse:
        return super().form_invalid(form)


class RegisterView(FormView):
    template_name = "register.html"
    form_class = RegistrationForm
    success_url = reverse_lazy("verify_email")

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save()
            send_verification_email(self.request, user)

        self.request.session["verification_email"] = user.email
        messages.success(
            self.request,
            "Tasdiqlash havolasi emailingizga yuborildi.",
        )
        return super().form_valid(form)


class PasswordResetView(TemplateView):
    template_name = "password_reset.html"


class VerifyEmailView(TemplateView):
    template_name = "verify_email.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["verification_email"] = self.request.session.get("verification_email")
        return context

    def post(self, request, *args, **kwargs):
        email = request.session.get("verification_email")
        user = User.objects.filter(email__iexact=email, is_active=False).first() if email else None

        if user is None:
            messages.error(request, "Tasdiqlanmagan hisob topilmadi. Qayta ro‘yxatdan o‘ting.")
            return redirect("register")

        send_verification_email(request, user)
        messages.success(request, "Yangi tasdiqlash havolasi yuborildi.")
        return redirect("verify_email")


class ActivateEmailView(View):
    template_name = "email_verification_invalid.html"

    def get(self, request, uidb64, token):
        user = self._get_user(uidb64)

        if user is not None and email_verification_token.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            request.session.pop("verification_email", None)
            messages.success(request, "Email tasdiqlandi. Endi hisobingizga kirishingiz mumkin.")
            return redirect("login")

        return render(request, self.template_name, status=HttpResponseBadRequest.status_code)

    @staticmethod
    def _get_user(uidb64):
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
            return User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
            return None


class DashboardView(TemplateView):
    template_name = "dashboard.html"


class ProfileView(TemplateView):
    template_name = "profile.html"


class SessionsView(TemplateView):
    template_name = "sessions.html"


class ForbiddenView(TemplateView):
    template_name = "403.html"
