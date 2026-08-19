from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.tokens import email_verification_token


def send_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    verification_path = reverse(
        "activate_email",
        kwargs={"uidb64": uid, "token": token},
    )
    verification_url = request.build_absolute_uri(verification_path)
    context = {
        "user": user,
        "verification_url": verification_url,
        "timeout_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
    }

    message = EmailMultiAlternatives(
        subject="AuthLab hisobingizni tasdiqlang",
        body=render_to_string("emails/verify_email.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(
        render_to_string("emails/verify_email.html", context),
        "text/html",
    )
    return message.send(fail_silently=False)
