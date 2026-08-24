from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms.forms import Form

from apps.models import User


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        error_messages = {
            "email": {
                "required": "Email manzilni kiriting.",
                "unique": "Bu email boshqa hisobga tegishli.",
            },
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        email_is_taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        if email_is_taken:
            raise ValidationError("Bu email boshqa hisobga tegishli.")
        return email


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput,
        error_messages={"required": "Hisobni o‘chirish uchun joriy parolni kiriting."},
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError("Joriy parol noto‘g‘ri.")
        return password


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


class LoginForm(Form):
    email = forms.EmailField(
        error_messages={
            "required": "Email manzilni kiriting.",
            "invalid": "Email manzil noto‘g‘ri.",
        }
    )

    password = forms.CharField(
        widget=forms.PasswordInput,
        error_messages={
            "required": "Parolni kiriting.",
        }
    )

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
