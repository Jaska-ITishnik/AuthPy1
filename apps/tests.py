import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
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
