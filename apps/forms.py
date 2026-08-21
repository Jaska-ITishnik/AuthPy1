from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms.models import ModelForm

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


class LoginForm(ModelForm):
    class Meta:
        model = User
        fields = "email", "password"
        error_messages = {
            "email": {
                "required": "Email manzilni kiriting.",
            },
            "password": {
                "required": "Parol majburiy kiriting.",
            },
        }

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def get_user(self):
        return self._cache_user

    def clean(self):
        cleaned_data = super().clean()
        if ('email' or 'password') not in cleaned_data.keys():
            raise ValidationError('Email and password cannot be blank')
        password = cleaned_data.get('password')
        email = cleaned_data.get("email")
        user = authenticate(email=email, password=password)
        if not user:
            raise ValidationError("Bunday foydalanuvchi mavjud emas!")
        self._cache_user = user
        return cleaned_data
