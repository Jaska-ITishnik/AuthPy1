from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.models import User


class RegistrationForm(UserCreationForm):
    terms = forms.BooleanField(
        required=True,
        error_messages={"required": "Ro‘yxatdan o‘tish uchun shartlarga rozilik bildiring."},
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email")
        error_messages = {
            "email": {
                "required": "Email manzilni kiriting.",
                "unique": "Bu email orqali avval hisob yaratilgan.",
            },
        }

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = False
        if commit:
            user.save()
        return user
