import re

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RegistrationFlowTests(TestCase):
    registration_data = {
        "first_name": "Jasurbek",
        "last_name": "Bekmirzayev",
        "email": "student@example.com",
        "password1": "SecurePass123!",
        "password2": "SecurePass123!",
        "terms": "on",
    }

    def test_registration_sends_html_verification_email_for_inactive_user(self):
        response = self.client.post(reverse("register"), self.registration_data)

        self.assertRedirects(response, reverse("verify_email"))
        user = get_user_model().objects.get(email="student@example.com")
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password("SecurePass123!"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student@example.com"])
        self.assertEqual(mail.outbox[0].alternatives[0].mimetype, "text/html")
        self.assertIn("Emailni tasdiqlash", mail.outbox[0].alternatives[0].content)

    def test_verification_link_activates_user_and_redirects_to_login_once(self):
        self.client.post(reverse("register"), self.registration_data)
        verification_url = re.search(
            r"http://testserver/verify-email/[^\s]+/",
            mail.outbox[0].body,
        ).group(0)

        response = self.client.get(verification_url)

        user = get_user_model().objects.get(email="student@example.com")
        self.assertTrue(user.is_active)
        self.assertRedirects(response, reverse("login"))

        reused_response = self.client.get(verification_url)
        self.assertEqual(reused_response.status_code, 400)

    def test_invalid_registration_does_not_create_user_or_send_email(self):
        invalid_data = self.registration_data | {"password2": "DifferentPass123!"}

        response = self.client.post(reverse("register"), invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match.")
        self.assertFalse(get_user_model().objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_verification_email_can_be_resent(self):
        self.client.post(reverse("register"), self.registration_data)

        response = self.client.post(reverse("verify_email"))

        self.assertRedirects(response, reverse("verify_email"))
        self.assertEqual(len(mail.outbox), 2)


class CurrentUserContextTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="aziza@example.com",
            password="SecurePass123!",
            first_name="Aziza",
            last_name="Karimova",
        )
        self.client.force_login(self.user)

    def test_all_authenticated_pages_receive_current_user_context(self):
        for url_name in ("dashboard", "profile", "sessions", "password_reset", "forbidden"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["current_user"], self.user)
                self.assertEqual(response.context["current_user_display_name"], "Aziza Karimova")
                self.assertEqual(response.context["current_user_initials"], "AK")

    def test_authenticated_templates_render_dynamic_user_data(self):
        dashboard_response = self.client.get(reverse("dashboard"))
        profile_response = self.client.get(reverse("profile"))

        self.assertContains(dashboard_response, "Aziza Karimova")
        self.assertContains(dashboard_response, "Salom, Aziza!")
        self.assertContains(dashboard_response, ">AK<")
        self.assertContains(profile_response, 'value="Aziza"')
        self.assertContains(profile_response, 'value="Karimova"')
        self.assertContains(profile_response, 'value="aziza@example.com"')

    def test_email_is_used_when_name_is_empty(self):
        self.user.first_name = ""
        self.user.last_name = ""
        self.user.save(update_fields=["first_name", "last_name"])

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["current_user_display_name"], "aziza@example.com")
        self.assertEqual(response.context["current_user_initials"], "A")
        self.assertContains(response, "Salom, aziza@example.com!")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ProfileCrudTests(TestCase):
    password = "SecurePass123!"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="aziza@example.com",
            password=self.password,
            first_name="Aziza",
            last_name="Karimova",
        )
        self.client.force_login(self.user)

    def test_profile_can_be_read_and_updated(self):
        response = self.client.post(
            reverse("profile"),
            {
                "action": "update_profile",
                "first_name": "Madina",
                "last_name": "Aliyeva",
                "email": self.user.email,
            },
        )

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Madina")
        self.assertEqual(self.user.last_name, "Aliyeva")
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_profile_rejects_another_users_email(self):
        get_user_model().objects.create_user(
            email="taken@example.com",
            password=self.password,
        )

        response = self.client.post(
            reverse("profile"),
            {
                "action": "update_profile",
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": "TAKEN@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bu email boshqa hisobga tegishli.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "aziza@example.com")

    def test_email_change_requires_verification_and_logs_user_out(self):
        response = self.client.post(
            reverse("profile"),
            {
                "action": "update_profile",
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": "new@example.com",
            },
        )

        self.assertRedirects(response, reverse("verify_email"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertFalse(self.user.is_active)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertEqual(self.client.session["verification_email"], "new@example.com")
        self.assertRedirects(self.client.get(reverse("dashboard")), f"{reverse('login')}?next=/")

    def test_password_can_be_changed_without_ending_current_session(self):
        new_password = "UpdatedPass456!"

        response = self.client.post(
            reverse("profile"),
            {
                "action": "change_password",
                "old_password": self.password,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_account_delete_requires_the_current_password(self):
        response = self.client.post(
            reverse("profile"),
            {"action": "delete_account", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Joriy parol noto‘g‘ri.")
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_account_can_be_deleted(self):
        response = self.client.post(
            reverse("profile"),
            {"action": "delete_account", "password": self.password},
        )

        self.assertRedirects(response, reverse("login"))
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
        self.assertRedirects(self.client.get(reverse("profile")), f"{reverse('login')}?next=/profile/")


class ActiveSessionsTests(TestCase):
    password = "SecurePass123!"
    chrome_ubuntu = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
    firefox_windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Firefox/126.0"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="aziza@example.com",
            password=self.password,
        )
        self.client.force_login(self.user)
        self.client.get(
            reverse("dashboard"),
            HTTP_USER_AGENT=self.chrome_ubuntu,
            REMOTE_ADDR="127.0.0.1",
        )

    def create_other_session(self):
        other_client = Client()
        other_client.force_login(self.user)
        other_client.get(
            reverse("dashboard"),
            HTTP_USER_AGENT=self.firefox_windows,
            REMOTE_ADDR="192.168.1.24",
        )
        return other_client

    def test_real_active_sessions_are_rendered(self):
        other_client = self.create_other_session()
        other_session_key = other_client.session.session_key

        response = self.client.get(reverse("sessions"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["active_sessions"]), 2)
        self.assertEqual(response.context["other_session_count"], 1)
        self.assertContains(response, "Chrome · Ubuntu")
        self.assertContains(response, "Firefox · Windows")
        self.assertContains(response, "127.0.0.1")
        self.assertContains(response, "192.168.1.24")
        self.assertNotContains(response, other_session_key)

    def test_another_session_can_be_revoked(self):
        self.create_other_session()
        sessions_response = self.client.get(reverse("sessions"))
        other_session = next(
            item for item in sessions_response.context["active_sessions"] if not item["is_current"]
        )

        response = self.client.post(
            reverse("sessions"),
            {"action": "revoke_session", "revoke_token": other_session["revoke_token"]},
        )

        self.assertRedirects(response, reverse("sessions"))
        self.assertEqual(Session.objects.count(), 1)
        self.assertTrue(Session.objects.filter(session_key=self.client.session.session_key).exists())

    def test_all_other_sessions_can_be_revoked(self):
        self.create_other_session()
        self.create_other_session()

        response = self.client.post(reverse("sessions"), {"action": "revoke_other_sessions"})

        self.assertRedirects(response, reverse("sessions"))
        self.assertEqual(Session.objects.count(), 1)
        self.assertTrue(Session.objects.filter(session_key=self.client.session.session_key).exists())

    def test_invalid_revoke_token_cannot_delete_sessions(self):
        self.create_other_session()

        response = self.client.post(
            reverse("sessions"),
            {"action": "revoke_session", "revoke_token": "invalid"},
        )

        self.assertRedirects(response, reverse("sessions"))
        self.assertEqual(Session.objects.count(), 2)
