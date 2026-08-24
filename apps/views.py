from django.contrib import messages
from django.contrib.auth import SESSION_KEY, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.emails import send_verification_email
from apps.forms import DeleteAccountForm, LoginForm, ProfileUpdateForm, RegistrationForm
from apps.models import User
from apps.session_utils import (
    SESSION_IP_KEY,
    SESSION_LAST_ACTIVITY_KEY,
    SESSION_USER_AGENT_KEY,
    describe_user_agent,
    make_session_revoke_token,
    record_session_activity,
)
from apps.tokens import email_verification_token


class CurrentUserContextMixin(LoginRequiredMixin):
    """Add consistently formatted current-user data to authenticated pages."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        full_name = user.get_full_name().strip()
        initials = f"{user.first_name[:1]}{user.last_name[:1]}".upper()

        context.update(
            {
                "current_user": user,
                "current_user_display_name": full_name or user.email,
                "current_user_initials": initials or user.email[:1].upper(),
            }
        )
        return context


class UserLoginView(FormView):
    template_name = "login.html"
    form_class = LoginForm

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        record_session_activity(self.request)
        return redirect('dashboard')

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class UserLogout(View):
    def post(self, request):
        logout(request)
        return redirect("login")


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


class PasswordResetView(CurrentUserContextMixin, TemplateView):
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


class DashboardView(CurrentUserContextMixin, TemplateView):
    template_name = "dashboard.html"


class ProfileView(CurrentUserContextMixin, TemplateView):
    template_name = "profile.html"
    profile_form_class = ProfileUpdateForm
    password_form_class = PasswordChangeForm
    delete_form_class = DeleteAccountForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("profile_form", self.profile_form_class(instance=self.request.user))
        context.setdefault("password_form", self.password_form_class(user=self.request.user))
        context.setdefault("delete_form", self.delete_form_class(user=self.request.user))
        return context

    def post(self, request, *args, **kwargs):
        action_handlers = {
            "update_profile": self._update_profile,
            "change_password": self._change_password,
            "delete_account": self._delete_account,
        }
        handler = action_handlers.get(request.POST.get("action"))
        if handler is None:
            return HttpResponseBadRequest("Noma’lum profil amali.")
        return handler()

    def _update_profile(self):
        old_email = self.request.user.email
        form = self.profile_form_class(self.request.POST, instance=self.request.user)
        if not form.is_valid():
            return self._render_invalid_form("profile_form", form)

        user = form.save(commit=False)
        email_changed = old_email.casefold() != user.email.casefold()

        if email_changed:
            user.is_active = False
            with transaction.atomic():
                user.save()
                send_verification_email(self.request, user)

            logout(self.request)
            self.request.session["verification_email"] = user.email
            messages.success(
                self.request,
                "Email yangilandi. Yangi manzilni tasdiqlash havolasi yuborildi.",
            )
            return redirect("verify_email")

        user.save()
        messages.success(self.request, "Profil ma’lumotlari saqlandi.")
        return redirect("profile")

    def _change_password(self):
        form = self.password_form_class(user=self.request.user, data=self.request.POST)
        if not form.is_valid():
            return self._render_invalid_form("password_form", form)

        user = form.save()
        update_session_auth_hash(self.request, user)
        messages.success(self.request, "Parol muvaffaqiyatli yangilandi.")
        return redirect("profile")

    def _delete_account(self):
        form = self.delete_form_class(self.request.POST, user=self.request.user)
        if not form.is_valid():
            return self._render_invalid_form("delete_form", form)

        user = self.request.user
        logout(self.request)
        user.delete()
        messages.success(self.request, "Hisobingiz butunlay o‘chirildi.")
        return redirect("login")

    def _render_invalid_form(self, form_name, form):
        context = self.get_context_data()
        context[form_name] = form
        return self.render_to_response(context)


class SessionsView(CurrentUserContextMixin, TemplateView):
    template_name = "sessions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_sessions = [
            self._serialize_session(session, data)
            for session, data in self._get_user_session_records()
        ]
        active_sessions.sort(key=lambda item: not item["is_current"])
        context["active_sessions"] = active_sessions
        context["other_session_count"] = sum(not item["is_current"] for item in active_sessions)
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "revoke_session":
            return self._revoke_session()
        if action == "revoke_other_sessions":
            return self._revoke_other_sessions()
        return HttpResponseBadRequest("Noma’lum sessiya amali.")

    def _get_user_session_records(self):
        records = []
        sessions = Session.objects.filter(expire_date__gt=timezone.now()).order_by("-expire_date")
        for session in sessions:
            data = session.get_decoded()
            if str(data.get(SESSION_KEY)) == str(self.request.user.pk):
                records.append((session, data))
        return records

    def _serialize_session(self, session, data):
        is_current = session.session_key == self.request.session.session_key
        user_agent = data.get(SESSION_USER_AGENT_KEY, "")
        ip_address = data.get(SESSION_IP_KEY, "")
        last_activity = self._parse_datetime(data.get(SESSION_LAST_ACTIVITY_KEY))

        if is_current:
            user_agent = user_agent or self.request.META.get("HTTP_USER_AGENT", "")
            ip_address = ip_address or self.request.META.get("REMOTE_ADDR", "")
            last_activity = last_activity or timezone.now()

        return {
            "device": describe_user_agent(user_agent),
            "ip_address": ip_address,
            "is_current": is_current,
            "last_activity": last_activity,
            "expires_at": session.expire_date,
            "revoke_token": make_session_revoke_token(self.request.user.pk, session.session_key),
        }

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return None
        try:
            return parse_datetime(value)
        except (TypeError, ValueError):
            return None

    def _revoke_session(self):
        submitted_token = self.request.POST.get("revoke_token", "")
        for session, _data in self._get_user_session_records():
            revoke_token = make_session_revoke_token(self.request.user.pk, session.session_key)
            if not constant_time_compare(revoke_token, submitted_token):
                continue

            if session.session_key == self.request.session.session_key:
                messages.error(self.request, "Joriy sessiyani bu yerdan tugatib bo‘lmaydi.")
            else:
                session.delete()
                messages.success(self.request, "Tanlangan sessiya tugatildi.")
            return redirect("sessions")

        messages.error(self.request, "Sessiya topilmadi yoki uning muddati tugagan.")
        return redirect("sessions")

    def _revoke_other_sessions(self):
        other_session_keys = [
            session.session_key
            for session, _data in self._get_user_session_records()
            if session.session_key != self.request.session.session_key
        ]
        deleted_count, _details = Session.objects.filter(session_key__in=other_session_keys).delete()
        if deleted_count:
            messages.success(self.request, f"{deleted_count} ta boshqa sessiya tugatildi.")
        else:
            messages.info(self.request, "Boshqa faol sessiyalar topilmadi.")
        return redirect("sessions")


class ForbiddenView(CurrentUserContextMixin, TemplateView):
    template_name = "403.html"
